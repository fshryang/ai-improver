"""应用入口：系统托盘 + 信号链。

信号链：
  ClipboardWatcher.text_copied(text)
      → MainWindow._on_text_copied(text)
      → SignPopup.popup(text)   （显示光标附近徽章）

  SignPopup.open_editor(text)
      → MainWindow._on_open_editor(text)
      → EditorPopup.set_text(text)  （打开编辑器 + 自动跑 AI）
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QSystemTrayIcon, QWidget

import config as config_mod
from clipboard_watcher import ClipboardWatcher
from editor_popup import EditorPopup
from settings_dialog import SettingsDialog
from sign_popup import SignPopup


class MainWindow(QWidget):
    """无主窗口的程序：托盘 + 弹窗，不需要可见主窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.resize(0, 0)

        # 子组件
        self._sign_popup = SignPopup()
        self._editor = EditorPopup()
        self._watcher: ClipboardWatcher | None = None

        # 信号连接
        self._sign_popup.open_editor.connect(self._on_open_editor)

    def start(self) -> None:
        """启动剪贴板监听。"""
        cfg = config_mod.load()
        min_length = cfg.get("min_text_length", 12)

        self._watcher = ClipboardWatcher(min_length=min_length)
        self._watcher.text_copied.connect(self._on_text_copied)
        self._watcher.start()

    def _on_text_copied(self, text: str) -> None:
        """剪贴板有新文本：显示徽章。"""
        self._sign_popup.popup(text)

    def _on_open_editor(self, text: str) -> None:
        """用户点了徽章：打开编辑器，自动跑一次。"""
        if not text.strip():
            return  # 剪贴板为空就不开窗
        self._editor.set_text(text)
        self._editor.show()
        self._editor.raise_()
        self._editor.activateWindow()

    def stop(self) -> None:
        if self._watcher is not None:
            self._watcher.stop()

    def open_settings(self) -> None:
        """打开设置对话框；保存成功后让编辑器丢弃缓存的 provider。"""
        dlg = SettingsDialog(self)
        # exec() 是模态阻塞，关闭后通过 result() 判断是否点了 Save
        if dlg.exec() == QDialog.Accepted:
            self._editor.invalidate_provider()


def _make_tray_icon() -> QIcon:
    """画一个简单的紫色 ✦ 图标（无外部资源依赖）。"""
    pix = QPixmap(64, 64)
    pix.fill()
    from PySide6.QtGui import QPainter, QColor, QFont

    p = QPainter(pix)
    p.setPen(QColor(0, 0, 0, 0))
    p.setBrush(QColor("#4B3FE3"))
    p.drawRoundedRect(0, 0, 64, 64, 16, 16)
    p.setPen(QColor("#FFFFFF"))
    f = QFont()
    f.setPointSize(32)
    f.setBold(True)
    p.setFont(f)
    p.drawText(pix.rect(), Qt.AlignCenter, "✦")
    p.end()
    return QIcon(pix)


def main() -> int:
    # 打包后首次运行：在 exe 同目录生成默认 config.json
    config_mod.ensure_config()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关掉弹窗不能退出托盘程序

    # 临时窗口（不可见，只是为了承载托盘）
    win = MainWindow()

    # 系统托盘
    tray = QSystemTrayIcon(_make_tray_icon(), parent=app)
    tray.setToolTip("AI Improver (clipboard watcher)")

    menu = QMenu()
    act_show = QAction("Open editor (paste mode)", menu)
    act_show.triggered.connect(
        lambda: win._on_open_editor(QApplication.clipboard().text() or "")
    )
    menu.addAction(act_show)

    act_settings = QAction("Settings...", menu)
    act_settings.triggered.connect(win.open_settings)
    menu.addAction(act_settings)

    menu.addSeparator()

    act_quit = QAction("Quit", menu)
    act_quit.triggered.connect(app.quit)
    menu.addAction(act_quit)

    tray.setContextMenu(menu)
    tray.show()

    # 启动剪贴板监听
    win.start()

    # 托盘单击：把当前剪贴板送进编辑器
    tray.activated.connect(
        lambda reason: (
            win._on_open_editor(QApplication.clipboard().text() or "")
            if reason == QSystemTrayIcon.Trigger
            else None
        )
    )

    # 程序退出时停掉后台线程
    app.aboutToQuit.connect(win.stop)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
