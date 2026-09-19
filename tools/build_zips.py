"""Package the Unknown skin and widgets service as zips for Kodi's "Install from zip file".

Usage:  py tools/build_zips.py
Writes dist/<addon id>-<version>.zip, with the add-on id as the zip's top folder as Kodi requires.
"""
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
ADDONS = ("skin.unknown", "service.unknown.widgets", "plugin.video.unknown.debrid")
EXCLUDED_DIRS = {"__pycache__", ".git", ".vscode", ".idea"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def addon_version(addon_dir):
    manifest = (addon_dir / "addon.xml").read_text(encoding="utf-8")
    return re.search(r'<addon\b[^>]*\sversion="([^"]+)"', manifest).group(1)


def build(addon_id, output_dir=DIST):
    addon_dir = ROOT / addon_id
    target = output_dir / "{}-{}.zip".format(addon_id, addon_version(addon_dir))
    files = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(addon_dir.rglob("*")):
            relative = path.relative_to(addon_dir)
            if path.is_dir() or EXCLUDED_DIRS.intersection(relative.parts) or path.suffix in EXCLUDED_SUFFIXES:
                continue
            archive.write(path, (Path(addon_id) / relative).as_posix())
            files += 1
    print("{:<45} {:>4} files  {:>7.1f} KB".format(target.name, files, target.stat().st_size / 1024))
    return target


def main():
    DIST.mkdir(exist_ok=True)
    for addon_id in ADDONS:
        build(addon_id)


if __name__ == "__main__":
    main()
