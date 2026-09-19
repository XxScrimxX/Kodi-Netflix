import datetime
import json
import os
import sqlite3
import time
import xml.etree.ElementTree as ET

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from resources.lib import debrid, names

PLAY_URL = "plugin://{}/play/{}/{}"
SCRAPER_MOVIES = "metadata.themoviedb.org.python"
SCRAPER_TVSHOWS = "metadata.tvshows.themoviedb.org.python"

STATUS_LABELS = {
    "magnet_conversion": "converting magnet",
    "waiting_files_selection": "awaiting file selection",
    "queued": "queued",
    "downloading": "downloading",
    "compressing": "compressing",
    "uploading": "uploading",
    "paused": "paused",
    "downloaded": "finished",
    "seeding": "seeding",
    "error": "error",
    "virus": "flagged as virus",
    "dead": "dead",
    "magnet_error": "magnet error",
}


def pretty_statuses(statuses):
    parts = []
    for status, count in sorted(statuses.items(), key=lambda item: -item[1]):
        parts.append("{} {}".format(count, STATUS_LABELS.get(status, status.replace("_", " "))))
    return ", ".join(parts) if parts else "none"


def data_dir():
    path = xbmcvfs.translatePath("special://profile/addon_data/{}/".format(debrid.ADDON_ID))
    if not xbmcvfs.exists(path):
        xbmcvfs.mkdirs(path)
    return path


def library_dir():
    path = os.path.join(data_dir(), "library")
    if not xbmcvfs.exists(path):
        xbmcvfs.mkdirs(path)
    return path


def manifest_path():
    return os.path.join(data_dir(), "manifest.json")


def load_manifest():
    try:
        with open(manifest_path(), "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def save_manifest(manifest):
    with open(manifest_path(), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=1)


def target_path(parsed):
    root = library_dir()
    if parsed["kind"] == "episode":
        show = names.safe_name(parsed["show"])
        return os.path.join(root, "TV Shows", show, "Season {:02d}".format(parsed["season"]),
                            "{} S{:02d}E{:02d}.strm".format(show, parsed["season"], parsed["episode"]))
    title = names.safe_name(parsed["title"])
    folder = "{} ({})".format(title, parsed["year"]) if parsed.get("year") else title
    return os.path.join(root, "Movies", folder, folder + ".strm")


def build_entries(token, torrent):
    entries = []
    info = debrid.torrent_info(token, torrent["id"])
    for media in info.get("files", []):
        if not media.get("selected") or not names.is_video(media["path"]) or names.is_sample(media["path"]):
            continue
        parsed = names.parse(media["path"], torrent.get("filename", ""))
        if parsed["kind"] == "episode":
            key = "episode|{}|{}|{}".format(parsed["show"].lower(), parsed["season"], parsed["episode"])
        else:
            key = "movie|{}|{}".format(parsed["title"].lower(), parsed.get("year"))
        entries.append({
            "key": key,
            "kind": parsed["kind"],
            "title": parsed.get("title", ""),
            "year": parsed.get("year"),
            "show": parsed.get("show", ""),
            "season": parsed.get("season"),
            "episode": parsed.get("episode"),
            "name": os.path.basename(media["path"]),
            "file_id": str(media["id"]),
            "torrent": torrent["id"],
            "torrent_name": torrent.get("filename", ""),
            "added": torrent.get("added", ""),
            "path": target_path(parsed),
            "play": PLAY_URL.format(debrid.ADDON_ID, torrent["id"], media["id"]),
        })
    return entries


def collect(token, progress=None):
    manifest = load_manifest()
    desired = {}
    taken = set()
    remote = debrid.torrents(token)
    statuses = {}
    for torrent in remote:
        status = torrent.get("status", "unknown")
        statuses[status] = statuses.get(status, 0) + 1
    downloaded = [t for t in remote if t.get("status") == "downloaded"]
    empty_downloaded = 0
    live_ids = set()
    total = len(downloaded)
    for position, torrent in enumerate(downloaded):
        torrent_id = torrent.get("id", "")
        live_ids.add(torrent_id)
        if progress:
            progress(int(position * 100 / max(total, 1)), torrent.get("filename", ""))
        cached = manifest.get(torrent_id)
        if cached and cached.get("filename") == torrent.get("filename"):
            entries = cached.get("files", [])
            added = cached.get("added") or torrent.get("added", "")
            for entry in entries:
                entry["added"] = added
        else:
            entries = build_entries(token, torrent)
            manifest[torrent_id] = {"filename": torrent.get("filename", ""),
                                    "added": torrent.get("added", ""),
                                    "files": entries}
        if not entries:
            empty_downloaded += 1
            debrid.log("Finished torrent with no playable files: {}".format(
                torrent.get("filename", torrent_id)), xbmc.LOGINFO)
            continue
        for entry in entries:
            if entry["key"] in taken:
                debrid.log("Skipping duplicate: {} from {}".format(entry["key"], entry["torrent_name"]), xbmc.LOGINFO)
                continue
            taken.add(entry["key"])
            desired[entry["play"]] = entry
    debrid.log("Torrents on Real-Debrid: {} total, {} finished, statuses {}".format(
        len(remote), len(downloaded), statuses), xbmc.LOGINFO)
    summary = {"total": len(remote), "downloaded": len(downloaded),
               "statuses": statuses, "empty_downloaded": empty_downloaded}
    return {tid: manifest[tid] for tid in live_ids if tid in manifest}, desired, summary


def write_strm(path, url):
    directory = os.path.dirname(path)
    if not xbmcvfs.exists(directory):
        xbmcvfs.mkdirs(directory)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(url)


def remove_empty_dirs(root):
    for current, dirs, files in os.walk(root, topdown=False):
        if current != root and not dirs and not files:
            try:
                os.rmdir(current)
            except OSError:
                pass


def _db_path():
    database_dir = xbmcvfs.translatePath("special://profile/Database/")
    try:
        candidates = [name for name in os.listdir(database_dir)
                      if name.startswith("MyVideos") and name.endswith(".db")]
    except OSError:
        return None
    if not candidates:
        return None
    return os.path.join(database_dir, sorted(candidates, reverse=True)[0])


def _update_sources_xml(targets):
    sources_path = xbmcvfs.translatePath("special://profile/sources.xml")
    try:
        tree = ET.parse(sources_path)
        root_el = tree.getroot()
    except (OSError, ET.ParseError):
        root_el = ET.Element("sources")
        for section in ("programs", "video", "music", "pictures", "files"):
            ET.SubElement(root_el, section)
        tree = ET.ElementTree(root_el)
    video = root_el.find("video")
    if video is None:
        video = ET.SubElement(root_el, "video")
    existing = {node.text for node in video.findall("source/path")}
    changed = False
    for path, _content, _scraper, name in targets:
        if path in existing:
            continue
        source = ET.SubElement(video, "source")
        ET.SubElement(source, "name").text = name
        ET.SubElement(source, "path", pathversion="1").text = path
        ET.SubElement(source, "allowsharing").text = "true"
        changed = True
    if changed:
        tree.write(sources_path, encoding="UTF-8", xml_declaration=True)


def _dir_exists(path):
    try:
        if os.path.isdir(path):
            return True
    except OSError:
        pass
    return bool(xbmcvfs.exists(path))


def ensure_sources():
    root = library_dir()
    targets = []
    for folder, content, scraper, name in (
            ("Movies", "movies", SCRAPER_MOVIES, "Unknown Debrid Movies"),
            ("TV Shows", "tvshows", SCRAPER_TVSHOWS, "Unknown Debrid TV Shows")):
        directory = os.path.join(root, folder)
        if _dir_exists(directory):
            targets.append((directory + os.sep, content, scraper, name))
        else:
            debrid.log("ensure_sources: source folder missing: {}".format(directory), xbmc.LOGWARNING)
    if not targets:
        debrid.log("ensure_sources: no source folders found under {}".format(root), xbmc.LOGWARNING)
        return [], True
    ok = True
    added = []
    db_file = _db_path()
    if db_file is None:
        ok = False
    else:
        try:
            connection = sqlite3.connect(db_file, timeout=10)
            try:
                for path, content, scraper, name in targets:
                    cursor = connection.execute("SELECT idPath FROM path WHERE strPath = ?", (path,))
                    if cursor.fetchone():
                        continue
                    connection.execute(
                        "INSERT INTO path (strPath, strContent, strScraper, scanRecursive, useFolderNames,"
                        " strSettings, noUpdate, exclude, allAudio) VALUES (?, ?, ?, ?, 0, '', 0, 0, 0)",
                        (path, content, scraper, 2147483647))
                    added.append(name)
            finally:
                connection.commit()
                connection.close()
        except sqlite3.Error as error:
            debrid.log("Could not register video sources: {}".format(error), xbmc.LOGWARNING)
            ok = False
    try:
        _update_sources_xml(targets)
    except (OSError, ET.ParseError) as error:
        debrid.log("Could not update sources.xml: {}".format(error), xbmc.LOGWARNING)
    debrid.log("ensure_sources: {} target(s), db_ok={}, added {}".format(len(targets), ok, added), xbmc.LOGINFO)
    return added, ok


def show_manual_sources_dialog():
    root = library_dir()
    xbmcgui.Dialog().ok(
        "Unknown Debrid",
        "The video sources could not be added automatically. Add them by hand under Videos, then Files,"
        " then Add videos:[CR][CR]{}[CR](content: Movies)[CR][CR]{}[CR](content: TV shows)".format(
            os.path.join(root, "Movies"), os.path.join(root, "TV Shows")))


def pending_dates_path():
    return os.path.join(data_dir(), "pending_dates.json")


def load_pending_dates():
    try:
        with open(pending_dates_path(), "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {"created": time.time(), "seen_scanning": False, "dates": {}}


def save_pending_dates(pending):
    with open(pending_dates_path(), "w", encoding="utf-8") as handle:
        json.dump(pending, handle)


def kodi_date(iso):
    if not iso:
        return ""
    stamp = iso.strip().replace("Z", "+0000")
    try:
        if "." in stamp:
            parsed = datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S.%f%z")
        else:
            parsed = datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S%z")
        return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return ""


def apply_pending_dates():
    pending = load_pending_dates()
    dates = pending.get("dates", {})
    if not dates:
        return
    db_file = _db_path()
    if db_file is None:
        return
    remaining = dict(dates)
    applied = 0
    try:
        connection = sqlite3.connect(db_file, timeout=10)
        try:
            for path, stamp in dates.items():
                directory, filename = os.path.split(path)
                cursor = connection.execute(
                    "UPDATE files SET dateAdded = ? WHERE strFilename = ? AND idPath IN"
                    " (SELECT idPath FROM path WHERE strPath = ?)",
                    (stamp, filename, directory + os.sep))
                if cursor.rowcount:
                    remaining.pop(path, None)
                    applied += cursor.rowcount
        finally:
            connection.commit()
            connection.close()
    except sqlite3.Error as error:
        debrid.log("Could not write added dates: {}".format(error), xbmc.LOGWARNING)
        return
    if remaining:
        pending["dates"] = remaining
        pending["attempts"] = pending.get("attempts", 0) + 1
        if pending["attempts"] >= 20:
            debrid.log("Gave up writing added dates for {} files".format(len(remaining)), xbmc.LOGWARNING)
            try:
                os.remove(pending_dates_path())
            except OSError:
                pass
            return
        save_pending_dates(pending)
    else:
        try:
            os.remove(pending_dates_path())
        except OSError:
            pass
    debrid.log("Applied Real-Debrid added dates to {} files".format(applied), xbmc.LOGINFO)


def run_sync(notify=False, interactive=False):
    window = xbmcgui.Window(10000)
    if window.getProperty("UnknownDebrid.Syncing"):
        return
    window.setProperty("UnknownDebrid.Syncing", "true")
    dialog = None
    progress = None
    if interactive:
        dialog = xbmcgui.DialogProgress()
        dialog.create("Unknown Debrid", "Listing Real-Debrid torrents...")
        progress = lambda percent, name: dialog.update(percent, "Reading: {}".format(name))
    try:
        token = debrid.ensure_token()
        old = load_manifest()
        manifest, desired, summary = collect(token, progress)
        old_paths = {entry["path"] for torrent in old.values() for entry in torrent.get("files", [])}
        new_paths = {entry["path"] for entry in desired.values()}
        removed = sorted(old_paths - new_paths)
        for path in removed:
            try:
                os.remove(path)
            except OSError:
                pass
        written = 0
        for entry in desired.values():
            if not os.path.exists(entry["path"]):
                write_strm(entry["path"], entry["play"])
                written += 1
        remove_empty_dirs(library_dir())
        save_manifest(manifest)
        settings = xbmcaddon.Addon()
        sources_added, sources_ok = ensure_sources()
        if (written or removed or sources_added) and settings.getSettingBool("auto_scan"):
            if removed and settings.getSettingBool("auto_clean"):
                xbmc.executebuiltin("CleanLibrary(video)")
            xbmc.executebuiltin("UpdateLibrary(video)")
        stamps = {}
        for entry in desired.values():
            stamp = kodi_date(entry.get("added"))
            if stamp:
                stamps[entry["path"]] = stamp
        if stamps:
            pending = load_pending_dates()
            pending.setdefault("dates", {}).update(stamps)
            pending["created"] = time.time()
            pending["seen_scanning"] = False
            save_pending_dates(pending)
        debrid.log("Sync complete: {} written, {} removed, {} tracked".format(written, len(removed), len(desired)),
                   xbmc.LOGINFO)
        if dialog:
            dialog.close()
        if interactive:
            if written or removed:
                xbmcgui.Dialog().notification(
                    "Unknown Debrid", "Library synced: {} new, {} removed".format(written, len(removed)),
                    xbmcgui.NOTIFICATION_INFO, 4000)
            elif not summary["total"]:
                xbmcgui.Dialog().ok(
                    "Unknown Debrid",
                    "Your Real-Debrid account has no torrents. Add one on real-debrid.com and sync again.")
            elif not summary["downloaded"]:
                xbmcgui.Dialog().ok(
                    "Unknown Debrid",
                    "Found {} torrent(s) on Real-Debrid, but none are finished yet:[CR][CR]{}[CR][CR]"
                    "Torrents can only be streamed once Real-Debrid has finished downloading them.".format(
                        summary["total"], pretty_statuses(summary["statuses"])))
            elif summary["empty_downloaded"]:
                xbmcgui.Dialog().ok(
                    "Unknown Debrid",
                    "{} finished torrent(s) contained no playable video files (samples or unsupported"
                    " types). Their names are in the log.".format(summary["empty_downloaded"]))
            else:
                xbmcgui.Dialog().notification("Unknown Debrid", "Library already in sync",
                                              xbmcgui.NOTIFICATION_INFO, 4000)
            if not sources_ok:
                show_manual_sources_dialog()
    except debrid.AuthExpired:
        if dialog:
            dialog.close()
        debrid.log("Sync skipped: no Real-Debrid account linked", xbmc.LOGINFO)
    except debrid.DebridError as error:
        if dialog:
            dialog.close()
        debrid.log("Sync failed: {}".format(error), xbmc.LOGWARNING)
        if notify or interactive:
            xbmcgui.Dialog().notification("Unknown Debrid", "Sync failed: {}".format(error),
                                          xbmcgui.NOTIFICATION_ERROR, 6000)
    finally:
        window.clearProperty("UnknownDebrid.Syncing")


def wipe():
    root = library_dir()
    for current, dirs, files in os.walk(root, topdown=False):
        for name in files:
            try:
                os.remove(os.path.join(current, name))
            except OSError:
                pass
        for name in dirs:
            try:
                os.rmdir(os.path.join(current, name))
            except OSError:
                pass
    save_manifest({})
    xbmc.executebuiltin("CleanLibrary(video)")


def apply_pending_if_due():
    pending = load_pending_dates()
    if not pending.get("dates"):
        return
    if xbmc.getCondVisibility("Library.IsScanningVideo"):
        if not pending.get("seen_scanning"):
            pending["seen_scanning"] = True
            save_pending_dates(pending)
        return
    if pending.get("seen_scanning") or time.time() - pending.get("created", 0) > 600:
        apply_pending_dates()


def _fold(name):
    return name.replace("(", " ").replace(")", " ").replace("-", " ").replace("_", " ")


def select_english_audio(abort=lambda: False):
    window = xbmcgui.Window(10000)
    flagged = window.getProperty("UnknownDebrid.Playback")
    if flagged:
        window.clearProperty("UnknownDebrid.Playback")
    elif not (xbmc.Player().getPlayingFile() or "").startswith("plugin://" + debrid.ADDON_ID):
        return
    if not xbmcaddon.Addon().getSettingBool("force_english_audio"):
        return
    player = xbmc.Player()
    streams = []
    for _ in range(6):
        request = {"jsonrpc": "2.0", "id": 1, "method": "Player.GetProperties",
                   "params": {"playerid": 1, "properties": ["audio"]}}
        try:
            reply = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
        except (ValueError, TypeError):
            return
        streams = (reply.get("result") or {}).get("audio") or []
        if streams:
            break
        if abort():
            return
        time.sleep(1)
    if not streams:
        debrid.log("Audio selection: no streams reported yet", xbmc.LOGDEBUG)
        return
    current = player.getAudioStream()
    target = None
    fallback = None
    for stream in streams:
        language = (stream.get("language") or "").lower()
        name = _fold((stream.get("name") or "").lower())
        english = language.startswith("en") or "english" in name or "eng" in name.split()
        if not english:
            continue
        if "commentary" in name:
            fallback = stream.get("index")
            continue
        target = stream.get("index")
        break
    if target is None:
        target = fallback
    if target is None:
        debrid.log("Audio selection: no English track found in [{}]".format(
            "; ".join("{}:{}".format(s.get("index"), s.get("name")) for s in streams)), xbmc.LOGINFO)
        return
    if target == current:
        return
    player.setAudioStream(target)
    still = player.getAudioStream()
    if still == current or still != target:
        debrid.log("Audio selection: switch to stream {} did not stick (now {})".format(target, still),
                   xbmc.LOGWARNING)
        return
    debrid.log("Forced English audio track (stream {})".format(target), xbmc.LOGINFO)


class DebridMonitor(xbmc.Monitor):
    def onAVStarted(self):
        try:
            select_english_audio(abort=self.abortRequested)
        except Exception as error:
            debrid.log("Audio track selection failed: {}".format(error), xbmc.LOGWARNING)

    def onPlayBackEnded(self):
        xbmcgui.Window(10000).clearProperty("UnknownDebrid.Playback")

    def onPlayBackStopped(self):
        xbmcgui.Window(10000).clearProperty("UnknownDebrid.Playback")

    def onPlayBackError(self):
        xbmcgui.Window(10000).clearProperty("UnknownDebrid.Playback")


def run_service():
    monitor = DebridMonitor()
    if monitor.waitForAbort(5):
        return
    for _ in range(60):
        if xbmc.getCondVisibility("Window.IsVisible(home)") or monitor.abortRequested():
            break
        if monitor.waitForAbort(1):
            return
    if not debrid.is_linked():
        from resources.lib import wizard
        wizard.link_account()
    elif xbmcaddon.Addon().getSettingBool("sync_on_startup"):
        run_sync()
    clean_marker = os.path.join(data_dir(), "clean_once.flag")
    if os.path.exists(clean_marker):
        debrid.log("Cleaning video library (orphaned entries purge)", xbmc.LOGINFO)
        xbmc.executebuiltin("CleanLibrary(video)")
        try:
            os.remove(clean_marker)
        except OSError:
            pass
    last_sync = time.monotonic()
    while not monitor.waitForAbort(30):
        interval = xbmcaddon.Addon().getSettingInt("sync_interval") * 60
        if interval <= 0:
            last_sync = time.monotonic()
            continue
        if time.monotonic() - last_sync >= interval:
            run_sync()
            last_sync = time.monotonic()
        apply_pending_if_due()
