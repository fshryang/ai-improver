"""设置对话框：在 App 内切 provider、填 API key、改模型/URL，保存写回 config.json。

UI 结构：
  顶部：Active provider 下拉框（deepseek/openai/anthropic/local）
  中部：QTabWidget，每个 provider 一个 tab，可同时编辑所有字段
  底部：Save / Cancel

  密码字段用 _SecretField：QLineEdit + Show/Hide 切换按钮，默认掩码。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import config as config_mod


# Provider 元数据：字段顺序、占位符、是否密码
# 加新 provider 只需在这里登记，UI 自动生成
_PROVIDER_FIELDS: dict[str, list[tuple[str, str, bool]]] = {
    "deepseek": [
        ("api_key", "sk-...", True),
        ("model", "deepseek-v4-flash", False),
        ("base_url", "https://api.deepseek.com/v1", False),
    ],
    "openai": [
        ("api_key", "sk-...", True),
        ("model", "gpt-4o-mini", False),
        ("base_url", "https://api.openai.com/v1", False),
    ],
    "anthropic": [
        ("api_key", "sk-ant-...", True),
        ("model", "claude-3-5-haiku-latest", False),
        ("base_url", "https://api.anthropic.com", False),
    ],
    "local": [
        ("base_url", "http://localhost:11434", False),
        ("model", "llama3.1:8b", False),
    ],
}


class _SecretField(QWidget):
    """密码字段：QLineEdit + Show/Hide 切换。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self._edit = QLineEdit()
        self._edit.setEchoMode(QLineEdit.Password)

        self._toggle = QPushButton("Show")
        self._toggle.setCheckable(True)
        self._toggle.setFixedWidth(64)
        self._toggle.toggled.connect(self._on_toggle)

        lay.addWidget(self._edit, stretch=1)
        lay.addWidget(self._toggle)

    def _on_toggle(self, checked: bool) -> None:
        self._edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
        self._toggle.setText("Hide" if checked else "Show")

    def text(self) -> str:
        return self._edit.text()

    def setText(self, t: str) -> None:  # noqa: N802  Qt 命名
        self._edit.setText(t)


class SettingsDialog(QDialog):
    """配置对话框。保存时写回 config.json 并 accept（主程序据此失效缓存）。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI Improver — Settings")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.resize(560, 380)

        # 字段引用：{ provider_name: { field_key: widget } }
        self._fields: dict[str, dict[str, QWidget]] = {}

        self._build_ui()
        self._load_current_values()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # 顶部：Active provider
        row = QHBoxLayout()
        lbl = QLabel("Active provider:")
        row.addWidget(lbl)
        self._combo = QComboBox()
        for name in _PROVIDER_FIELDS:
            self._combo.addItem(name)
        row.addWidget(self._combo, stretch=1)
        root.addLayout(row)

        # 中部：每个 provider 一个 tab
        self._tabs = QTabWidget()
        for name, fields in _PROVIDER_FIELDS.items():
            page = QWidget()
            form = QFormLayout(page)
            form.setContentsMargins(12, 12, 12, 12)
            form.setSpacing(10)

            self._fields[name] = {}
            for key, placeholder, is_secret in fields:
                if is_secret:
                    widget = _SecretField()
                else:
                    widget = QLineEdit()
                widget.setText("")  # 占位用 placeholder
                # 设置 placeholder 的统一接口
                if isinstance(widget, QLineEdit):
                    widget.setPlaceholderText(placeholder)
                else:  # _SecretField 内部的 QLineEdit
                    widget._edit.setPlaceholderText(placeholder)
                form.addRow(key, widget)
                self._fields[name][key] = widget

            self._tabs.addTab(page, name)
        root.addWidget(self._tabs, stretch=1)

        # 底部：保存 / 取消
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _load_current_values(self) -> None:
        """从 config.json 读出当前值填进各字段。"""
        cfg = config_mod.load()
        active = config_mod.get_active_provider_name(cfg)
        # 设下拉
        i = self._combo.findText(active)
        if i >= 0:
            self._combo.setCurrentIndex(i)

        # 填每个 provider 的字段
        for name, fields in _PROVIDER_FIELDS.items():
            pcfg = config_mod.get_provider_config(cfg, name)
            for key, _, _ in fields:
                val = pcfg.get(key, "")
                widget = self._fields[name][key]
                widget.setText(val)

    def _on_save(self) -> None:
        """读所有字段 → 写回 config.json → accept。

        只覆盖用户实际填写的非空值；空字符串视为"没改"，保留原值。
        这样用户只填了 api_key 不会把 model/base_url 清掉。
        """
        cfg = config_mod.load()
        cfg["active_provider"] = self._combo.currentText()

        providers = cfg.setdefault("providers", {})
        for name, fields in _PROVIDER_FIELDS.items():
            pcfg = providers.setdefault(name, {})
            for key, _, _ in fields:
                new_val = self._fields[name][key].text().strip()
                if new_val:  # 只在非空时覆盖
                    pcfg[key] = new_val

        try:
            config_mod.save(cfg)
        except OSError as e:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(self, "Save failed", f"Could not write config.json:\n{e}")
            return

        self.accept()

