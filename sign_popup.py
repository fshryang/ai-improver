"""提示牌：检测到可改进文本时，在光标附近弹出的小徽章。

点击它会触发 open_editor 信号，主程序接到信号后打开完整编辑器。
设计：无边框、半透明、悬浮在最顶层，鼠标进入变亮、点击即触发。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QCursor, QPalette
from PySide6.QtWidgets import QLabel, QWidget


class SignPopup(QWidget):
    """光标附近的小提示牌。点击后发 open_editor(text)。"""

    open_editor = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._text: str = ""

        # 无边框、悬浮、最顶层、不入任务栏、不抢焦点
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        # 内容：一个圆形 / 胶囊状的"改进文本"徽章
        self._label = QLabel("✦ Improve", self)
        f = QFont()
        f.setPointSize(10)
        f.setBold(True)
        self._label.setFont(f)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setFixedHeight(28)
        self._label.setStyleSheet(
            "QLabel {"
            "  background: rgba(75, 63, 227, 230);"
            "  color: white;"
            "  border-radius: 14px;"
            "  padding: 4px 14px;"
            "}"
            "QLabel:hover {"
            "  background: rgba(96, 84, 241, 255);"
            "}"
        )

        # 自动隐藏计时器：5 秒没人点就消失
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(5000)
        self._hide_timer.timeout.connect(self.hide)

    def popup(self, text: str) -> None:
        """显示徽章，绑定新文本，定位到光标右下方。"""
        self._text = text
        # 让 label 自适应宽度
        self._label.adjustSize()
        self._label.resize(self._label.sizeHint())
        self.resize(self._label.sizeHint())

        cursor_pos = QCursor.pos()
        self.move(cursor_pos.x() + 16, cursor_pos.y() + 16)
        self.show()
        self._hide_timer.start()

    def mousePressEvent(self, event) -> None:
        """点击徽章：发信号打开编辑器，自己隐藏。"""
        if event.button() == Qt.LeftButton:
            self._hide_timer.stop()
            self.hide()
            self.open_editor.emit(self._text)
        super().mousePressEvent(event)
