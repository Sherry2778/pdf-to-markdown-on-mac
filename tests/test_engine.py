import json
from pathlib import Path
import subprocess
import sys

import pytest

from pdf_to_markdown.engine import ConversionError, convert_pdf, publish_markdown


def test_real_conversion(sample_pdf, tmp_path):
    result = convert_pdf(sample_pdf, tmp_path)
    assert result.pages == 1
    assert result.characters > 0
    assert "A local PDF conversion test" in Path(result.output).read_text()
    assert not list(tmp_path.glob(".markdown-*.tmp"))


def test_collision_and_unicode(tmp_path):
    first = publish_markdown(tmp_path, "学习 '笔记'", "# Original")
    second = publish_markdown(tmp_path, "学习 '笔记'", "# Second")
    assert first.read_text() == "# Original\n"
    assert second.name == "学习 '笔记' (2).md"


def test_cancelled_publish_cleans_temporary_file(tmp_path, monkeypatch):
    def interrupt(*_args):
        raise KeyboardInterrupt
    monkeypatch.setattr("pdf_to_markdown.engine.os.link", interrupt)
    with pytest.raises(KeyboardInterrupt):
        publish_markdown(tmp_path, "test", "# Complete")
    assert list(tmp_path.iterdir()) == []


def test_reject_invalid_pdf(tmp_path):
    source = tmp_path / "fake.pdf"
    source.write_text("plain text")
    with pytest.raises(ConversionError, match="有效"):
        convert_pdf(source, tmp_path)
    assert not list(tmp_path.glob("*.md"))


def test_blank_pdf_does_not_create_empty_output(tmp_path):
    from conftest import make_pdf
    source = make_pdf(tmp_path / "blank.pdf", "")
    with pytest.raises(ConversionError, match="没有提取"):
        convert_pdf(source, tmp_path)
    assert not list(tmp_path.glob("*.md"))


def test_worker_json_contract(sample_pdf, tmp_path):
    entry = Path(__file__).parents[1] / "app.py"
    result = subprocess.run(
        [sys.executable, str(entry), "--worker", str(sample_pdf), str(tmp_path)],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    message = json.loads(result.stdout)
    assert message["ok"]
    assert Path(message["output"]).is_file()
