"""编辑器弹窗：核心 UI。

功能：
- 双栏：原文（只读） / 改进版（可编辑）
- Diff 高亮：绿色=新增文本, 红色删除线=原文里被删的文本
- 悬停同步：鼠标光标下的词在另一栏里也高亮
- 模式切换 / Re-run / Copy / 关闭

AI 调用走 QThread worker（ImproveWorker），通过 Qt 信号回主线程。
"""
from __future__ import annotations

import asyncio
import difflib

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import ai_engine
import config as config_mod


# —— 颜色常量 ——
COLOR_ADDED = "#22c55e"          # 绿色: 新增文本
COLOR_REMOVED = "#ef4444"        # 红色: 删除文本
COLOR_REMOVED_BG = "#fee2e2"     # 浅红背景
COLOR_ADDED_BG = "#dcfce7"       # 浅绿背景
COLOR_HOVER = "#fef08a"          # 黄色: 悬停同步高亮


# —— Diff 高亮器 ——
class DiffHighlighter(QSyntaxHighlighter):
    """用 difflib 比较原文和改进版，在两端分别高亮增删。

    两端各有一个实例：original 实例高亮"被删的词"，improved 实例高亮"新增的词"。
    """

    def __init__(self, document, side: str) -> None:
        super().__init__(document)
        self._side = side          # "original" 或 "improved"
        self._other_text: str = ""
        self._ranges: list[tuple[int, int]] = []  # [(start, length), ...]

    def set_other(self, other_text: str) -> None:
        """设置对照文本，重算 diff。"""
        self._other_text = other_text
        self._recompute()
        self.rehighlight()

    def clear(self) -> None:
        self._other_text = ""
        self._ranges = []
        self.rehighlight()

    def _recompute(self) -> None:
        if not self._other_text.strip():
            self._ranges = []
            return
        doc_text = self.document().toPlainText()
        sm = difflib.SequenceMatcher(None, doc_text, self._other_text)
        self._ranges = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if self._side == "original":
                # original 里的 "删除" 是 tag=='delete' 或 tag=='replace' 的前半段
                if tag == "delete" or tag == "replace":
                    self._ranges.append((i1, i2 - i1))
            else:  # improved
                # improved 里的 "新增" 是 tag=='insert' 或 tag=='replace' 的后半段
                if tag == "insert" or tag == "replace":
                    self._ranges.append((j1, j2 - j1))

    def highlightBlock(self, text: str) -> None:
        """QSyntaxHighlighter 接口：给当前 block 应用格式。"""
        if not self._ranges:
            return
        block_start = self.currentBlock().position()
        for start, length in self._ranges:
            # 只高亮与当前 block 重叠的部分
            if start + length <= block_start:
                continue
            if start >= block_start + len(text):
                break
            local_start = max(0, start - block_start)
            local_end = min(len(text), start + length - block_start)
            local_len = local_end - local_start
            if local_len <= 0:
                continue
            fmt = QTextCharFormat()
            if self._side == "original":
                # 删除: 红底 + 删除线
                fmt.setBackground(QColor(COLOR_REMOVED_BG))
                fmt.setForeground(QColor(COLOR_REMOVED))
                fmt.setFontStrikeOut(True)
            else:
                # 新增: 绿底
                fmt.setBackground(QColor(COLOR_ADDED_BG))
                fmt.setForeground(QColor("#166534"))  # 深绿文字
            self.setFormat(local_start, local_len, fmt)


# —— 悬停高亮器 ——
class HoverHighlighter:
    """对一个 QPlainTextEdit 做整文档级的词级高亮（用 setExtraSelections）。"""

    def __init__(self, editor: QPlainTextEdit) -> None:
        self._editor = editor
        self._fmt = QTextCharFormat()
        self._fmt.setBackground(QColor(COLOR_HOVER))
        self._cursor = QTextCursor(editor.document())

    def highlight_range(self, start: int, length: int) -> None:
        """高亮 [start, start+length) 区间；length<=0 则清除。"""
        selections: list[QTextEdit.ExtraSelection] = []
        if length > 0:
            sel = QTextEdit.ExtraSelection()
            sel.format = self._fmt
            c = QTextCursor(self._editor.document())
            c.setPosition(start)
            c.setPosition(start + length, QTextCursor.KeepAnchor)
            sel.cursor = c
            selections.append(sel)
        self._editor.setExtraSelections(selections)

    def clear(self) -> None:
        self._editor.setExtraSelections([])


# —— 后台 Worker ——
class ImproveWorker(QThread):
    """后台 worker：在子线程跑 async provider.improve()，发 result/error 信号。"""

    result_ready = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, provider, text: str, mode: str) -> None:
        super().__init__()
        self._provider = provider
        self._text = text
        self._mode = mode

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                self._provider.improve(self._text, self._mode)
            )
            self.result_ready.emit(result)
        except Exception as e:
            self.error_occurred.emit(f"[Error] {e}")
        finally:
            loop.close()


# —— 主窗口 ——
class EditorPopup(QMainWindow):
    """主编辑器窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self._original_text: str = ""
        self._mode: str = "improve"
        self._provider = None
        self._worker: ImproveWorker | None = None
        self._diff_enabled = True

        self.setWindowTitle("AI Improver")
        self.resize(900, 520)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # —— 顶部：标题 + 模式 + Diff 开关 ——
        top = QHBoxLayout()
        title = QLabel("AI Improver")
        f = QFont()
        f.setPointSize(14)
        f.setBold(True)
        title.setFont(f)
        top.addWidget(title)
        top.addStretch()

        self._btn_diff = QPushButton("Diff ✓")
        self._btn_diff.setCheckable(True)
        self._btn_diff.setChecked(True)
        self._btn_diff.clicked.connect(self._toggle_diff)
        top.addWidget(self._btn_diff)

        self._btn_improve = QPushButton("Improve")
        self._btn_improve.setCheckable(True)
        self._btn_improve.setChecked(True)
        self._btn_improve.clicked.connect(lambda: self._switch_mode("improve"))
        top.addWidget(self._btn_improve)

        self._btn_detect = QPushButton("Detect")
        self._btn_detect.setCheckable(True)
        self._btn_detect.clicked.connect(lambda: self._switch_mode("detect"))
        top.addWidget(self._btn_detect)
        root.addLayout(top)

        # —— 中部：双栏 ——
        body = QHBoxLayout()
        body.setSpacing(12)

        left_col = QVBoxLayout()
        left_label = QLabel("Original")
        left_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        left_col.addWidget(left_label)
        self._original_box = QPlainTextEdit()
        self._original_box.setReadOnly(True)
        self._original_box.setStyleSheet(
            "QPlainTextEdit {"
            "  background: #f7f7f8;"
            "  color: #171717;"
            "  border: 1px solid rgba(0,0,0,0.12);"
            "  border-radius: 8px;"
            "  padding: 8px;"
            "}"
        )
        left_col.addWidget(self._original_box)
        body.addLayout(left_col)

        right_col = QVBoxLayout()
        right_label = QLabel("Improved")
        right_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        right_col.addWidget(right_label)
        self._result_box = QPlainTextEdit()
        self._result_box.setStyleSheet(
            "QPlainTextEdit {"
            "  background: #ffffff;"
            "  color: #171717;"
            "  border: 1px solid rgba(75, 63, 227, 0.4);"
            "  border-radius: 8px;"
            "  padding: 8px;"
            "}"
        )
        right_col.addWidget(self._result_box)
        body.addLayout(right_col)

        root.addLayout(body, stretch=1)

        # —— 底部：操作按钮 ——
        bottom = QHBoxLayout()
        self._btn_rerun = QPushButton("Re-run")
        self._btn_rerun.clicked.connect(self._on_rerun)
        bottom.addWidget(self._btn_rerun)

        self._btn_copy = QPushButton("Copy improved")
        self._btn_copy.clicked.connect(self._on_copy)
        bottom.addWidget(self._btn_copy)

        bottom.addStretch()

        self._status = QLabel("Ready")
        self._status.setStyleSheet("color: #6b7280; font-size: 12px;")
        bottom.addWidget(self._status)

        self._btn_close = QPushButton("Close")
        self._btn_close.clicked.connect(self.close)
        bottom.addWidget(self._btn_close)
        root.addLayout(bottom)

        # —— 高亮器 ——
        self._orig_diff = DiffHighlighter(self._original_box.document(), "original")
        self._impr_diff = DiffHighlighter(self._result_box.document(), "improved")
        self._orig_hover = HoverHighlighter(self._original_box)
        self._impr_hover = HoverHighlighter(self._result_box)

        # —— 选中同步信号 ——
        self._original_box.selectionChanged.connect(
            lambda: self._on_selection_changed(self._original_box, self._result_box, "original")
        )
        self._result_box.selectionChanged.connect(
            lambda: self._on_selection_changed(self._result_box, self._original_box, "improved")
        )

    # —— 对外接口 ——
    def set_text(self, text: str) -> None:
        self._original_text = text
        self._original_box.setPlainText(text)
        self._result_box.setPlainText("")
        self._orig_diff.clear()
        self._impr_diff.clear()
        self._on_rerun()

    def invalidate_provider(self) -> None:
        self._provider = None

    # —— 内部逻辑 ——
    def _toggle_diff(self) -> None:
        self._diff_enabled = self._btn_diff.isChecked()
        self._btn_diff.setText("Diff ✓" if self._diff_enabled else "Diff ✗")
        if self._diff_enabled:
            self._orig_diff.set_other(self._result_box.toPlainText())
            self._impr_diff.set_other(self._original_box.toPlainText())
        else:
            self._orig_diff.clear()
            self._impr_diff.clear()

    def _switch_mode(self, mode: str) -> None:
        self._mode = mode
        self._btn_improve.setChecked(mode == "improve")
        self._btn_detect.setChecked(mode == "detect")

    def _get_provider(self):
        if self._provider is None:
            cfg = config_mod.load()
            self._provider = ai_engine.get_provider(cfg)
        return self._provider

    def _on_rerun(self) -> None:
        if not self._original_text.strip():
            self._status.setText("No text to process.")
            return
        if self._worker is not None and self._worker.isRunning():
            return

        self._status.setText("Working…")
        self._btn_rerun.setEnabled(False)
        self._result_box.setPlainText("")
        self._orig_diff.clear()
        self._impr_diff.clear()

        try:
            provider = self._get_provider()
        except Exception as e:
            self._status.setText(f"Config error: {e}")
            self._btn_rerun.setEnabled(True)
            return

        self._worker = ImproveWorker(provider, self._original_text, self._mode)
        self._worker.result_ready.connect(self._on_result)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

    def _on_result(self, result: str) -> None:
        self._result_box.setPlainText(result)
        self._btn_rerun.setEnabled(True)
        self._status.setText("Done")
        # Diff 高亮
        if self._diff_enabled:
            self._orig_diff.set_other(result)
            self._impr_diff.set_other(self._original_text)

    def _on_error(self, msg: str) -> None:
        self._result_box.setPlainText(msg)
        self._btn_rerun.setEnabled(True)
        self._status.setText("Error")

    def _on_copy(self) -> None:
        text = self._result_box.toPlainText()
        if text and not text.startswith("[Error]"):
            QGuiApplication.clipboard().setText(text)
            self._status.setText("Copied.")

    def _on_selection_changed(
        self, source: QPlainTextEdit, target: QPlainTextEdit, source_side: str
    ) -> None:
        """选中文本时：用 difflib 找到目标里的对应区间，黄色高亮。"""
        cursor = source.textCursor()
        if not cursor.hasSelection():
            # 没选中 → 清掉目标高亮
            if target is self._original_box:
                self._orig_hover.clear()
            else:
                self._impr_hover.clear()
            return

        src_text = source.toPlainText()
        tgt_text = target.toPlainText()
        if not src_text or not tgt_text:
            return

        sel_start = cursor.selectionStart()
        sel_end = cursor.selectionEnd()

        # 用 difflib 映射位置
        sm = difflib.SequenceMatcher(None, src_text, tgt_text)
        tgt_start, tgt_end = self._map_range(sm, sel_start, sel_end, source_side)

        if target is self._original_box:
            self._orig_hover.highlight_range(tgt_start, tgt_end - tgt_start)
        else:
            self._impr_hover.highlight_range(tgt_start, tgt_end - tgt_start)

    @staticmethod
    def _map_range(
        sm: difflib.SequenceMatcher,
        start: int,
        end: int,
        source_side: str,
    ) -> tuple[int, int]:
        """把 source 的 [start, end) 区间映射到 target 里的对应区间。

        核心思路:用 difflib 比较「选中文本」与「目标全文」,找出匹配块,
        再只保留最密集的匹配簇(避免跨段落的零碎匹配),取该簇首尾位置。
        这比逐 opcode 块遍历更鲁棒 —— 能正确处理 delete/insert 导致的映射断裂。
        """
        a_text = sm.a  # original
        b_text = sm.b  # improved
        axis_i = source_side == "original"
        src_text = a_text if axis_i else b_text
        tgt_text = b_text if axis_i else a_text
        selected = src_text[start:end]

        if not selected.strip():
            return 0, 0

        sub_sm = difflib.SequenceMatcher(None, tgt_text, selected)

        # 收集所有有意义的匹配块 (>=3 字符)
        matches: list[tuple[int, int, int, int]] = []  # (tgt_start, tgt_end, sel_start, sel_end)
        for i, j, n in sub_sm.get_matching_blocks():
            if n >= 3:
                matches.append((i, i + n, j, j + n))

        if not matches:
            # 退而求其次:最长匹配(不限长度)
            best = sub_sm.find_longest_match(0, len(tgt_text), 0, len(selected))
            if best.size > 0:
                return best.a, best.a + best.size
            return 0, 0

        # 按 target 位置排序,贪心合并相邻(间距 <= 阈值)的匹配块成"簇"
        matches.sort()
        cluster_threshold = max(len(selected) // 2, 50)
        clusters: list[list[tuple[int, int, int, int]]] = []
        current_cluster = [matches[0]]

        for m in matches[1:]:
            gap = m[0] - current_cluster[-1][1]
            if gap <= cluster_threshold:
                current_cluster.append(m)
            else:
                clusters.append(current_cluster)
                current_cluster = [m]
        clusters.append(current_cluster)

        # 选包含最多选中文本字符的簇
        best_cluster = max(
            clusters, key=lambda c: sum(m[3] - m[2] for m in c)
        )

        tgt_start = best_cluster[0][0]
        tgt_end = best_cluster[-1][1]
        if tgt_end < tgt_start:
            tgt_end = tgt_start
        return tgt_start, tgt_end
