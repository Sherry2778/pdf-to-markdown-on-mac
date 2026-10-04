"""Draw an original app icon; no downloaded artwork or fonts are bundled."""

from pathlib import Path
import os
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPen


def create_icon(destination: Path):
    app = QGuiApplication.instance() or QGuiApplication([])
    iconset = destination.with_suffix(".iconset")
    iconset.mkdir(parents=True, exist_ok=True)
    for points in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            size = points * scale
            canvas = QImage(size, size, QImage.Format_ARGB32)
            canvas.fill(Qt.transparent)
            painter = QPainter(canvas); painter.setRenderHint(QPainter.Antialiasing)
            painter.scale(size / 1024, size / 1024)
            gradient = QLinearGradient(100, 40, 850, 1000)
            gradient.setColorAt(0, QColor("#9182EC")); gradient.setColorAt(1, QColor("#4A399E"))
            painter.setPen(Qt.NoPen); painter.setBrush(gradient)
            painter.drawRoundedRect(QRectF(34, 34, 956, 956), 210, 210)
            painter.setBrush(QColor("#BDB3F2"))
            painter.drawRoundedRect(QRectF(230, 196, 500, 630), 60, 60)
            painter.setBrush(QColor("#FFFFFF"))
            painter.drawRoundedRect(QRectF(285, 155, 510, 630), 60, 60)
            painter.setPen(QPen(QColor("#A59BDB"), 36, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(385, 295, 680, 295)
            painter.drawLine(385, 390, 590, 390)
            painter.setPen(QPen(QColor("#6653C3"), 55, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawLine(540, 490, 540, 690)
            painter.drawLine(450, 610, 540, 700)
            painter.drawLine(540, 700, 630, 610)
            painter.end()
            suffix = "@2x" if scale == 2 else ""
            canvas.save(str(iconset / f"icon_{points}x{points}{suffix}.png"))
    subprocess.run(["/usr/bin/iconutil", "-c", "icns", str(iconset), "-o", str(destination)], check=True)


if __name__ == "__main__":
    create_icon(Path(sys.argv[1]))
