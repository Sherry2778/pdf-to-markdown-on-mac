import time
from pathlib import Path

from PySide6.QtTest import QTest

from pdf_to_markdown.gui import MainWindow
from conftest import make_pdf


def wait_until(predicate, seconds=20):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(20)
    assert predicate(), "GUI did not reach the expected state"


def test_batch_continues_after_failure_and_previews(qt_app, tmp_path):
    first = make_pdf(tmp_path / "first.pdf")
    bad = tmp_path / "bad.pdf"; bad.write_text("invalid")
    last = make_pdf(tmp_path / "last.pdf", "Final document")
    output = tmp_path / "output"
    window = MainWindow()
    window.output_folder = output
    window.add_paths([first, first, bad, last])
    assert len(window.items) == 3  # Duplicate additions are ignored.
    window.start_batch()
    wait_until(lambda: not window.busy)
    assert [i.state for i in window.items] == ["success", "failed", "success"]
    assert window.progress.value() == 3
    assert window.retry_button.isEnabled()
    window.table.selectRow(2)
    assert "Final document" in window.preview.toPlainText()
    assert Path(window.items[2].result["output"]).exists()
    # Repair the failed input and retry; successful documents are not repeated.
    make_pdf(bad, "Repaired")
    window.retry_failed()
    wait_until(lambda: not window.busy)
    assert all(i.state == "success" for i in window.items)
    assert len(list(output.glob("*.md"))) == 3
    window.close()


def test_cancel_stops_queue_and_can_resume(qt_app, tmp_path):
    first = make_pdf(tmp_path / "first.pdf")
    second = make_pdf(tmp_path / "second.pdf")
    window = MainWindow()
    window.output_folder = tmp_path / "output"
    window.add_paths([first, second])
    window.start_batch()
    window.cancel_batch()
    wait_until(lambda: not window.busy)
    assert all(i.state == "cancelled" for i in window.items)
    assert not list(window.output_folder.glob("*.md"))
    window.retry_failed()
    wait_until(lambda: not window.busy)
    assert all(i.state == "success" for i in window.items)
    window.close()
