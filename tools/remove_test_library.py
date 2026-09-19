import glob
import os
import shutil
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

USERDATA = Path(os.environ["APPDATA"]) / "Kodi" / "userdata"
MARKER = Path(os.environ["APPDATA"]) / "Kodi" / "userdata" / "addon_data" / "plugin.video.unknown.debrid" / "clean_once.flag"


def remove_test_sources(sources_path):
    if not sources_path.exists():
        print("  sources.xml missing, skipping")
        return
    tree = ET.parse(sources_path)
    removed = []
    for video in tree.getroot().findall("video"):
        for source in list(video.findall("source")):
            path_el = source.find("path")
            if path_el is None or path_el.text is None:
                continue
            normalized = path_el.text.replace("/", "\\")
            if "test-library" not in normalized:
                continue
            name_el = source.find("name")
            removed.append(name_el.text if name_el is not None else normalized)
            video.remove(source)
    if removed:
        tree.write(sources_path, encoding="UTF-8", xml_declaration=True)
    print("  test sources removed: {}".format(", ".join(removed) if removed else "none"))


def remove_test_path_rows(database_dir):
    any_db = False
    for db in sorted(database_dir.glob("MyVideos*.db")):
        any_db = True
        backup = db.with_suffix(db.suffix + ".bak")
        shutil.copy2(db, backup)
        connection = sqlite3.connect(str(db), timeout=10)
        try:
            rows = connection.execute("SELECT COUNT(*) FROM path WHERE strPath LIKE ?", ("%test-library%",)).fetchone()[0]
            connection.execute("DELETE FROM path WHERE strPath LIKE ?", ("%test-library%",))
            connection.commit()
            print("  {}: removed {} test path row(s), backup at {}".format(db.name, rows, backup.name))
        finally:
            connection.close()
    if not any_db:
        print("  no video database found")


def main():
    print("Removing test library:\n")
    remove_test_sources(USERDATA / "sources.xml")
    remove_test_path_rows(USERDATA / "Database")
    if MARKER.exists():
        os.remove(MARKER)
    with open(MARKER, "w") as handle:
        handle.write("1")
    print("\nMarker set - Kodi will auto-clean the orphaned library entries on next boot.")
    print("Real-Debrid sources and synced files are untouched.")


if __name__ == "__main__":
    main()