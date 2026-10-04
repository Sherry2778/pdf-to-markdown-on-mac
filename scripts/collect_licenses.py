"""Collect actual installed distributions' license files for a local build."""

from importlib.metadata import distribution
from pathlib import Path
import json
import shutil
import sys

from packaging.requirements import Requirement


def collect(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    pending = [Requirement("markitdown[pdf]"), Requirement("PySide6-Essentials"), Requirement("pyinstaller")]
    visited = set()
    records = {}
    while pending:
        requirement = pending.pop()
        key = (requirement.name.lower().replace("_", "-"), tuple(sorted(requirement.extras)))
        if key in visited:
            continue
        visited.add(key)
        package = distribution(requirement.name)
        name = package.metadata["Name"]
        licenses = []
        for file in package.files or []:
            lower = str(file).lower()
            if "/licenses/" in lower or Path(lower).name.startswith(("license", "copying", "notice")):
                source = Path(package.locate_file(file))
                if source.is_file():
                    safe = str(file).replace("../", "").lstrip("/")
                    target = output / name / safe
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
                    licenses.append(str(target.relative_to(output)))
        records[name] = {
            "version": package.version,
            "license": package.metadata.get("License-Expression") or package.metadata.get("License", ""),
            "project_urls": package.metadata.get_all("Project-URL", []),
            "files": licenses,
        }
        for raw in package.requires or []:
            child = Requirement(raw)
            extras = {"", *requirement.extras}
            if child.marker is None or any(child.marker.evaluate({"extra": extra}) for extra in extras):
                pending.append(child)
    # Python license text is also available through the standard license helper.
    import builtins
    builtins.license._Printer__setup()
    (output / "PYTHON-LICENSE.txt").write_text(
        "\n".join(builtins.license._Printer__lines) + "\n", encoding="utf-8"
    )
    (output / "packages.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return records


if __name__ == "__main__":
    collect(Path(sys.argv[1]))
