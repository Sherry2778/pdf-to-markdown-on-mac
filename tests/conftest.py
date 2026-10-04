from pathlib import Path
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def make_pdf(path: Path, text="A local PDF conversion test"):
    """Create a synthetic, single-page PDF without third-party fixtures."""
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(data)
    data.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n")
    path.write_bytes(data)
    return path


@pytest.fixture
def sample_pdf(tmp_path):
    return make_pdf(tmp_path / "example.pdf")


@pytest.fixture(scope="session")
def qt_app(tmp_path_factory):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication
    folder = str(tmp_path_factory.mktemp("qt-settings"))
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, folder)
    return QApplication.instance() or QApplication([])
