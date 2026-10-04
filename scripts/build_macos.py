"""Build an independent app in a temporary local directory.

No developer machine paths are embedded in the distributed launcher.
"""

from pathlib import Path
import os
import platform
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pdf_to_markdown.config import APP_ID, APP_NAME
from collect_licenses import collect


def build():
    if sys.platform != "darwin":
        raise SystemExit("Build the macOS app on macOS.")
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pdf-markdown-build-") as temporary:
        staging = Path(temporary)
        notices = staging / "ThirdPartyNotices"
        collect(notices)
        shutil.copyfile(ROOT / "THIRD_PARTY_NOTICES.md", notices / "README.md")
        shutil.copyfile(ROOT / "LICENSE", notices / "APP-LICENSE.txt")
        icon = staging / "icon.icns"
        subprocess.run([sys.executable, str(ROOT / "scripts/make_icon.py"), str(icon)], check=True)
        command = [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--windowed", "--onedir", "--name", APP_NAME,
            "--osx-bundle-identifier", APP_ID, "--icon", str(icon),
            "--distpath", str(staging / "dist"), "--workpath", str(staging / "build"),
            "--specpath", str(staging),
            "--paths", str(ROOT), "--add-data", f"{notices}:ThirdPartyNotices",
            "--copy-metadata", "markitdown",
            "--collect-data", "magika", "--collect-data", "pdfminer",
            str(ROOT / "app.py"),
        ]
        subprocess.run(command, cwd=ROOT, check=True)
        app = staging / "dist" / f"{APP_NAME}.app"
        subprocess.run(["/usr/bin/xattr", "-cr", str(app)], check=True)
        subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)], check=True)
        archive = destination / f"pdf-to-markdown-on-mac-{platform.machine()}.zip"
        subprocess.run([
            "/usr/bin/ditto", "--norsrc", "--noextattr", "-c", "-k",
            "--keepParent", str(app), str(archive),
        ], check=True)
        installed = destination / app.name
        if installed.exists():
            shutil.rmtree(installed)
        shutil.copytree(app, installed, symlinks=True)
        print(f"App: {installed}\nArchive: {archive}")


if __name__ == "__main__":
    build()
