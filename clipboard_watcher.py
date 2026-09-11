"""剪贴板监听：后台 QThread 轮询 Windows 剪贴板，检测到新文本就发信号。

设计要点：
- 不能在主线程轮询，否则 UI 卡顿；用 QThread + QTimer
- 用上次文本做去重，避免重复触发
- 文本太短（< min_length）直接忽略，过滤掉复制单个单词等噪声
"""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal, QTimer
from PySide6.QtGui import QClipboard, QGuiApplication


class ClipboardWatcher(QThread):
    """后台线程：轮询剪贴板，发 text_copied(text) 信号。"""

    text_copied = Signal(str)  # 新文本就绪

    def __init__(
        self,
        min_length: int = 12,
        poll_interval_ms: int = 250,
    ) -> None:
        super().__init__()
        self.min_length = min_length
        self.poll_interval_ms = poll_interval_ms

        self._last_text: str = ""
        self._timer: QTimer | None = None
        self._clipboard: QClipboard = QGuiApplication.clipboard()

    def run(self) -> None:
        """线程入口：创建 QTimer 并 exec 事件循环。"""
        self._timer = QTimer()
        self._timer.setInterval(self.poll_interval_ms)
        self._timer.timeout.connect(self._poll)
        self._timer.start()
        self.exec()

    def _poll(self) -> None:
        """每次轮询：读剪贴板，文本变化且够长就发信号。"""
        text = self._clipboard.text()
        if not text:
            return
        if len(text.strip()) < self.min_length:
            return
        if text == self._last_text:
            return
        self._last_text = text
        self.text_copied.emit(text)

    def stop(self) -> None:
        """停止监听并退出线程事件循环。"""
        if self._timer is not None:
            self._timer.stop()
        self.quit()
        self.wait(2000)
