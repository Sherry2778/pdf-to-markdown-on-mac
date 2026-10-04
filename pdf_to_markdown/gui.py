"""Qt desktop interface. Conversion runs in cancellable child processes."""

from dataclasses import dataclass, field
import json
from pathlib import Path
import sys

from PySide6.QtCore import QProcess, QSettings, QStandardPaths, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QFileDialog, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from . import __version__
from .config import APP_NAME, ORGANIZATION

STATUS_LABELS = {
    "pending": "等待转换", "running": "正在转换…", "success": "已完成",
    "warning": "完成 · 请检查", "failed": "未完成", "cancelled": "已取消",
}


@dataclass
class QueueItem:
    path: Path
    state: str = "pending"
    result: dict = field(default_factory=dict)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1120, 750)
        self.setMinimumSize(900, 620)
        self.setAcceptDrops(True)
        self.settings = QSettings(ORGANIZATION, "Desktop")
        default = str(Path(QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)) / "Markdown")
        self.output_folder = Path(self.settings.value("output_folder", default))
        self.items = []
        self.batch = []
        self.batch_total = 0
        self.batch_done = 0
        self.active_index = None
        self.process = None
        self.stdout = bytearray()
        self.busy = False
        self.cancel_requested = False
        self.close_requested = False
        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(30, 24, 30, 22)
        layout.setSpacing(18)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        eyebrow = QLabel("PDF → MARKDOWN")
        eyebrow.setObjectName("eyebrow")
        title = QLabel(APP_NAME)
        title.setObjectName("title")
        subtitle = QLabel("把 PDF 变成便于阅读、整理和使用的 Markdown 文档。")
        subtitle.setObjectName("muted")
        titles.addWidget(eyebrow); titles.addWidget(title); titles.addWidget(subtitle)
        header.addLayout(titles); header.addStretch()
        badge = QLabel("●  本地转换")
        badge.setObjectName("badge")
        header.addWidget(badge, alignment=Qt.AlignTop)
        layout.addLayout(header)
        tools = QHBoxLayout()
        self.add_button = QPushButton("＋ 添加 PDF")
        self.folder_button = QPushButton("添加文件夹")
        self.remove_button = QPushButton("移除所选")
        self.clear_button = QPushButton("清空")
        self.add_button.clicked.connect(self.pick_files)
        self.folder_button.clicked.connect(self.pick_folder)
        self.remove_button.clicked.connect(self.remove_selected)
        self.clear_button.clicked.connect(self.clear_items)
        for button in (self.add_button, self.folder_button, self.remove_button, self.clear_button):
            tools.addWidget(button)
        tools.addStretch()
        self.count_label = QLabel("0 个文件")
        self.count_label.setObjectName("muted")
        tools.addWidget(self.count_label)
        layout.addLayout(tools)
        splitter = QSplitter(Qt.Horizontal)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["文档", "大小", "状态"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 76); self.table.setColumnWidth(2, 128)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(54)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.itemSelectionChanged.connect(self.show_preview)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        self.empty_hint = QLabel("拖入 PDF，或点击「添加 PDF」\n支持多选；每份文档单独保存。")
        self.empty_hint.setObjectName("empty")
        self.empty_hint.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.empty_hint)
        left_layout.addWidget(self.table)
        splitter.addWidget(left)
        right = QFrame()
        right.setObjectName("previewPanel")
        preview_layout = QVBoxLayout(right)
        preview_layout.setContentsMargins(18, 14, 18, 14)
        preview_header = QHBoxLayout()
        preview_header.addWidget(QLabel("Markdown 预览"))
        preview_header.addStretch()
        self.copy_button = QPushButton("复制全文")
        self.copy_button.clicked.connect(self.copy_markdown)
        self.copy_button.setEnabled(False)
        preview_header.addWidget(self.copy_button)
        preview_layout.addLayout(preview_header)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QFont("Menlo", 12))
        self.preview.setPlaceholderText("转换后，点击左侧的文件查看结果。\n\n预览以文本显示，便于检查标题、表格和内容。")
        preview_layout.addWidget(self.preview)
        self.detail = QLabel("文件内容保留在你的电脑上。")
        self.detail.setWordWrap(True)
        self.detail.setObjectName("muted")
        preview_layout.addWidget(self.detail)
        splitter.addWidget(right)
        splitter.setSizes([570, 440])
        layout.addWidget(splitter, stretch=1)
        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("保存到"))
        self.output_label = QLabel(str(self.output_folder))
        self.output_label.setObjectName("muted")
        self.output_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.output_label.setToolTip(str(self.output_folder))
        output_row.addWidget(self.output_label, stretch=1)
        self.choose_output_button = QPushButton("更改文件夹")
        self.choose_output_button.clicked.connect(self.pick_output)
        self.open_output_button = QPushButton("打开")
        self.open_output_button.clicked.connect(self.open_output)
        output_row.addWidget(self.choose_output_button)
        output_row.addWidget(self.open_output_button)
        layout.addLayout(output_row)
        footer = QHBoxLayout()
        progress_layout = QVBoxLayout()
        self.summary = QLabel("准备好后，开始转换。")
        self.progress = QProgressBar()
        self.progress.setRange(0, 1); self.progress.setValue(0)
        self.progress.setTextVisible(False); self.progress.setFixedHeight(6)
        progress_layout.addWidget(self.summary)
        progress_layout.addWidget(self.progress)
        footer.addLayout(progress_layout, stretch=1)
        self.retry_button = QPushButton("重试未完成")
        self.retry_button.clicked.connect(self.retry_failed)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.cancel_batch)
        self.cancel_button.setVisible(False)
        self.start_button = QPushButton("开始转换")
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self.start_batch)
        for button in (self.retry_button, self.cancel_button, self.start_button):
            footer.addWidget(button)
        layout.addLayout(footer)
        bottom = QHBoxLayout()
        note = QLabel("适用于文字型 PDF · 扫描件暂不支持 OCR · 请检查复杂表格与公式")
        note.setObjectName("footnote")
        bottom.addWidget(note); bottom.addStretch()
        about = QPushButton(f"关于 v{__version__}")
        about.setFlat(True)
        about.clicked.connect(self.show_about)
        bottom.addWidget(about)
        layout.addLayout(bottom)
        QShortcut(QKeySequence.Open, self, activated=self.pick_files)
        self.setStyleSheet("""
            QWidget { font-family: -apple-system, 'PingFang SC'; font-size: 13px; color: #253047; }
            #root { background: #F4F6FA; }
            #eyebrow { color: #6C5DCC; font-size: 11px; font-weight: 700; letter-spacing: 2px; }
            #title { font-size: 27px; font-weight: 700; color: #182036; }
            #muted, #footnote { color: #748095; }
            #footnote { font-size: 11px; }
            #badge { background: #E7F3EE; color: #287455; padding: 7px 12px; border-radius: 13px; }
            QPushButton { background: white; border: 1px solid #DCE1EB; border-radius: 7px; padding: 8px 13px; }
            QPushButton:hover { background: #EFF0FC; border-color: #B5ADE4; }
            QPushButton:disabled { color: #A7ADBA; background: #F1F3F7; }
            #primary { background: #6C5DCC; color: white; border-color: #6C5DCC; padding: 10px 24px; font-weight: 600; }
            #primary:hover { background: #5D4EBD; }
            #primary:disabled { background: #B8B1DA; border-color: #B8B1DA; }
            QTableWidget { background: white; border: 1px solid #E0E4ED; border-radius: 10px; selection-background-color: #EEEAFB; selection-color: #30245F; }
            QHeaderView::section { background: #F9FAFC; color: #728096; border: none; border-bottom: 1px solid #E0E4ED; padding: 10px; text-align: left; }
            QTableWidget::item { padding: 8px; border-bottom: 1px solid #F1F3F7; }
            #previewPanel { background: white; border: 1px solid #E0E4ED; border-radius: 10px; }
            QPlainTextEdit { background: white; border: none; color: #43516B; }
            #empty { background: #EEEFF8; color: #79829B; padding: 26px; border-radius: 9px; }
            QProgressBar { border: none; border-radius: 3px; background: #E1E4EE; }
            QProgressBar::chunk { background: #8576DD; border-radius: 3px; }
            QSplitter::handle { background: transparent; width: 16px; }
        """)
        self.refresh_controls()

    def pick_files(self):
        if self.busy:
            return
        files, _ = QFileDialog.getOpenFileNames(self, "选择 PDF（可多选）", "", "PDF 文件 (*.pdf *.PDF)")
        self.add_paths(files)

    def pick_folder(self):
        if not self.busy:
            folder = QFileDialog.getExistingDirectory(self, "添加文件夹中的 PDF（不含子文件夹）")
            if folder:
                self.add_paths([folder])

    def add_paths(self, paths):
        if self.busy:
            return
        known = {item.path for item in self.items}
        for raw_path in paths:
            path = Path(raw_path).expanduser()
            candidates = sorted(path.iterdir()) if path.is_dir() else [path]
            for candidate in candidates:
                if not candidate.is_file() or candidate.suffix.lower() != ".pdf":
                    continue
                candidate = candidate.resolve()
                if candidate in known:
                    continue
                known.add(candidate)
                self.items.append(QueueItem(candidate))
                row = self.table.rowCount()
                self.table.insertRow(row)
                name = QTableWidgetItem(candidate.name)
                name.setToolTip(str(candidate))
                self.table.setItem(row, 0, name)
                size = candidate.stat().st_size / 1024
                self.table.setItem(row, 1, QTableWidgetItem(
                    f"{size / 1024:.1f} MB" if size >= 1024 else f"{size:.0f} KB"
                ))
                self.table.setItem(row, 2, QTableWidgetItem(STATUS_LABELS["pending"]))
        self.refresh_controls()

    def dragEnterEvent(self, event):
        if not self.busy and event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.add_paths([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])
        event.acceptProposedAction()

    def remove_selected(self):
        if self.busy:
            return
        rows = sorted({item.row() for item in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row); self.items.pop(row)
        self.show_preview(); self.refresh_controls()

    def clear_items(self):
        if not self.busy:
            self.table.setRowCount(0); self.items.clear()
            self.preview.clear(); self.progress.setValue(0)
            self.summary.setText("准备好后，开始转换。")
            self.refresh_controls()

    def pick_output(self):
        folder = QFileDialog.getExistingDirectory(self, "选择保存文件夹", str(self.output_folder))
        if folder:
            self.output_folder = Path(folder)
            self.settings.setValue("output_folder", folder)
            self.output_label.setText(folder); self.output_label.setToolTip(folder)

    def open_output(self):
        if self.output_folder.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_folder)))

    def set_state(self, index, state, result=None):
        self.items[index].state = state
        if result is not None:
            self.items[index].result = result
        cell = self.table.item(index, 2)
        cell.setText(STATUS_LABELS[state])
        cell.setToolTip(self.items[index].result.get("error", ""))

    def start_batch(self):
        if self.busy:
            return
        self.batch = [i for i, item in enumerate(self.items) if item.state == "pending"]
        if not self.batch:
            return
        try:
            self.output_folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            QMessageBox.warning(self, "无法保存", "无法创建保存文件夹，请选择其他位置。")
            return
        self.busy = True; self.cancel_requested = False
        self.batch_total = len(self.batch); self.batch_done = 0
        self.progress.setRange(0, self.batch_total); self.progress.setValue(0)
        self.refresh_controls()
        self.next_file()

    def next_file(self):
        if self.cancel_requested or not self.batch:
            self.finish_batch()
            return
        self.active_index = self.batch.pop(0)
        item = self.items[self.active_index]
        self.set_state(self.active_index, "running")
        self.summary.setText(f"正在转换 {self.batch_done + 1} / {self.batch_total}：{item.path.name}")
        self.stdout = bytearray()
        self.process = QProcess(self)
        process = self.process
        process.readyReadStandardOutput.connect(self.read_stdout)
        process.readyReadStandardError.connect(lambda: process.readAllStandardError())
        process.finished.connect(self.process_finished)
        process.errorOccurred.connect(self.process_error)
        if getattr(sys, "frozen", False):
            args = ["--worker", str(item.path), str(self.output_folder)]
        else:
            entry = Path(__file__).resolve().parents[1] / "app.py"
            args = [str(entry), "--worker", str(item.path), str(self.output_folder)]
        process.start(sys.executable, args)

    def read_stdout(self):
        if self.process is not None:
            self.stdout.extend(bytes(self.process.readAllStandardOutput()))

    def process_error(self, error):
        if error == QProcess.FailedToStart and self.active_index is not None:
            self.set_state(self.active_index, "failed", {"error": "转换组件无法启动，请重新安装应用。"})
            self.active_index = None
            self.batch_done += 1
            self.progress.setValue(self.batch_done)
            self.process.deleteLater(); self.process = None
            QTimer.singleShot(0, self.next_file)

    def process_finished(self, code, _exit_status):
        if self.active_index is None:
            return
        self.read_stdout()
        try:
            result = json.loads(self.stdout.decode("utf-8").strip())
        except (ValueError, UnicodeError):
            result = {"ok": False, "error": "转换进程意外结束，请重试。"}
        if result.get("ok") and code == 0:
            state = "warning" if result.get("warnings") else "success"
        elif self.cancel_requested or result.get("cancelled"):
            state = "cancelled"
        else:
            state = "failed"
        completed_index = self.active_index
        self.set_state(completed_index, state, result)
        self.active_index = None
        self.batch_done += 1
        self.progress.setValue(self.batch_done)
        process = self.process; self.process = None; process.deleteLater()
        self.table.selectRow(completed_index)
        self.show_preview()
        QTimer.singleShot(0, self.next_file)

    def cancel_batch(self):
        if not self.busy:
            return
        self.cancel_requested = True
        self.cancel_button.setEnabled(False)
        self.summary.setText("正在取消，已完成的文件会保留。")
        if self.process is not None:
            process = self.process
            process.terminate()
            QTimer.singleShot(2500, lambda: self.kill_if_current(process))

    def kill_if_current(self, process):
        if self.process is process and process.state() != QProcess.NotRunning:
            process.kill()

    def finish_batch(self):
        if self.cancel_requested:
            for index in self.batch:
                self.set_state(index, "cancelled")
        self.batch = []
        self.busy = False
        successful = sum(item.state in ("success", "warning") for item in self.items)
        failed = sum(item.state == "failed" for item in self.items)
        cancelled = sum(item.state == "cancelled" for item in self.items)
        self.summary.setText(f"已完成 {successful} 个 · 未完成 {failed} 个 · 已取消 {cancelled} 个")
        self.refresh_controls()
        if self.close_requested:
            self.close()

    def retry_failed(self):
        if self.busy:
            return
        for index, item in enumerate(self.items):
            if item.state in ("failed", "cancelled"):
                self.set_state(index, "pending", {})
        self.start_batch()

    def refresh_controls(self):
        for button in (self.add_button, self.folder_button, self.remove_button,
                       self.clear_button, self.choose_output_button):
            button.setEnabled(not self.busy)
        self.start_button.setEnabled(not self.busy and any(i.state == "pending" for i in self.items))
        self.retry_button.setEnabled(not self.busy and any(i.state in ("failed", "cancelled") for i in self.items))
        self.cancel_button.setVisible(self.busy); self.cancel_button.setEnabled(self.busy)
        self.count_label.setText(f"{len(self.items)} 个文件")
        self.empty_hint.setVisible(not self.items)

    def selected_item(self):
        row = self.table.currentRow()
        return self.items[row] if 0 <= row < len(self.items) else None

    def show_preview(self):
        self.copy_button.setEnabled(False)
        item = self.selected_item()
        if item is None:
            self.preview.clear(); self.detail.setText("文件内容保留在你的电脑上。")
            return
        result = item.result
        output = result.get("output")
        if output and Path(output).is_file():
            try:
                with Path(output).open(encoding="utf-8") as stream:
                    text = stream.read(200_001)
            except OSError:
                self.preview.clear(); self.detail.setText("无法读取结果，文件可能已移动。")
                return
            truncated = len(text) > 200_000
            self.preview.setPlainText(text[:200_000])
            self.copy_button.setEnabled(True)
            note = f"{result.get('pages', 0)} 页 · {result.get('characters', 0):,} 字符 · {result.get('elapsed', 0)} 秒"
            if truncated:
                note += "\n预览仅显示前 200,000 字符，保存的文件包含完整结果。"
            if result.get("warnings"):
                note += "\n" + "\n".join(result["warnings"])
            self.detail.setText(note)
        else:
            self.preview.clear()
            self.detail.setText(result.get("error", STATUS_LABELS[item.state]))

    def copy_markdown(self):
        item = self.selected_item()
        if item and item.result.get("output"):
            try:
                QApplication.clipboard().setText(Path(item.result["output"]).read_text(encoding="utf-8"))
                self.detail.setText("已复制完整 Markdown。")
            except OSError:
                self.detail.setText("无法读取结果，文件可能已移动。")

    def show_about(self):
        QMessageBox.information(
            self, "关于",
            f"{APP_NAME}  {__version__}\n\n"
            "基于 Microsoft MarkItDown，采用 AI 辅助开发。\n"
            "本地提取 PDF 文字，不调用在线大模型。\n"
            "每个文件单独转换，结果保留在所选文件夹。\n\n"
            "扫描件暂不支持 OCR；图像内容不会变成文字。\n"
            "复杂表格、公式、双栏排版请对照原文检查。"
        )

    def closeEvent(self, event):
        if self.busy:
            choice = QMessageBox.question(self, "正在转换", "取消当前任务并退出？")
            if choice == QMessageBox.Yes:
                self.close_requested = True; self.cancel_batch()
            event.ignore()
        else:
            event.accept()


def run():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORGANIZATION)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()
