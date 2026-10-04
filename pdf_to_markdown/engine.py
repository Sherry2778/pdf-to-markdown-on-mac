"""Local PDF conversion; deliberately has no GUI or network client."""

from dataclasses import asdict, dataclass
from pathlib import Path
import os
import tempfile
import time


class ConversionError(Exception):
    """An error that can be shown directly to the user."""


@dataclass(frozen=True)
class ConversionResult:
    source: str
    output: str
    pages: int
    characters: int
    elapsed: float
    warnings: tuple[str, ...]

    def to_dict(self):
        return asdict(self)


def publish_markdown(folder: Path, stem: str, content: str) -> Path:
    """Publish a complete file without overwriting any existing destination.

    A hard link is an atomic, exclusive publish on the local macOS filesystem.
    The temporary file is always removed, including on graceful cancellation.
    """
    fd, temporary_name = tempfile.mkstemp(prefix=".markdown-", suffix=".tmp", dir=folder)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content.rstrip() + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        number = 1
        while True:
            suffix = "" if number == 1 else f" ({number})"
            destination = folder / f"{stem}{suffix}.md"
            try:
                os.link(temporary, destination)
                return destination
            except FileExistsError:
                number += 1
            except OSError as error:
                raise ConversionError(
                    "无法在这个文件夹安全保存。请检查写入权限，或选择 Mac 本地文件夹。"
                ) from error
    finally:
        temporary.unlink(missing_ok=True)


def convert_pdf(source: Path, folder: Path) -> ConversionResult:
    started = time.monotonic()
    source = Path(source)
    folder = Path(folder)
    if not source.is_file() or source.suffix.lower() != ".pdf":
        raise ConversionError("PDF 文件不存在或格式不受支持。")
    if not folder.is_dir():
        raise ConversionError("保存文件夹不存在，请重新选择。")
    if source.stat().st_size == 0:
        raise ConversionError("这个 PDF 是空文件。")
    with source.open("rb") as stream:
        if b"%PDF-" not in stream.read(1024):
            raise ConversionError("文件不是有效的 PDF，可能已损坏。")

    # Import lazily: launching the GUI does not load the conversion libraries.
    import pdfplumber
    from pdfminer.pdfdocument import PDFPasswordIncorrect
    from markitdown import StreamInfo
    from markitdown.converters import PdfConverter

    warnings = []
    try:
        with pdfplumber.open(source) as document:
            pages = len(document.pages)
            image_only = []
            for index, page in enumerate(document.pages, 1):
                if not page.chars and page.images:
                    image_only.append(index)
                page.close()
        with source.open("rb") as stream:
            result = PdfConverter().convert(
                stream,
                StreamInfo(extension=".pdf", mimetype="application/pdf", filename=source.name),
            )
    except PDFPasswordIncorrect as error:
        raise ConversionError("PDF 已加密，请先解锁后再转换。") from error
    except Exception as error:
        raise ConversionError("无法解析这个 PDF；文件可能损坏或受限制。") from error
    content = result.markdown
    if not content.strip():
        raise ConversionError("没有提取到文字。扫描版 PDF 需要 OCR，当前版本暂不支持。")
    if image_only:
        shown = "、".join(map(str, image_only[:12]))
        remainder = "等" if len(image_only) > 12 else ""
        warnings.append(f"第 {shown}{remainder} 页可能是扫描页，文字未被提取。")
    output = publish_markdown(folder, source.stem, content)
    return ConversionResult(
        source=str(source), output=str(output), pages=pages,
        characters=len(content), elapsed=round(time.monotonic() - started, 2),
        warnings=tuple(warnings),
    )
