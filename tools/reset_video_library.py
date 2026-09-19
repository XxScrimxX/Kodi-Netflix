import glob
import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

USERDATA = Path(os.environ["APPDATA"]) / "Kodi" / "userdata"
TEST_LIBRARY = Path(__file__).resolve().parent.parent / "test-library"


def remove_test_sources(sources_path):
    if not sources_path.exists():
        print("no sources.xml, skipping")
        return
    tree = ET.parse(sources_path)
    removed = []
    for video in tree.getroot().findall("video"):
        for source in list(video.findall("source")):
            path = source.find("path")
            if path is not None and path.text and "test-library" in path.text.replace("/", "\\"):
                removed.append(source.find("name").text if source.find("name") is not None else path.text)
                video.remove(source)
    if removed:
        tree.write(sources_path, encoding="UTF-8", xml_declaration=True)
    print("sources removed: {}".format(", ".join(removed) if removed else "none found"))


def reset_video_databases(database_dir):
    for db in sorted(database_dir.glob("MyVideos*.db")):
        backup = db.with_suffix(db.suffix + ".bak")
        shutil.copy2(db, backup)
        db.unlink()
        print("reset {} (backup: {})".format(db.name, backup.name))


def main():
    if not USERDATA.exists():
        raise SystemExit("Kodi userdata not found at {}".format(USERDATA))
    remove_test_sources(USERDATA / "sources.xml")
    reset_video_databases(USERDATA / "Database")
    print("\nDone. Start Kodi: the Debrid service re-registers its sources and rescans automatically.")


if __name__ == "__main__":
    main()
