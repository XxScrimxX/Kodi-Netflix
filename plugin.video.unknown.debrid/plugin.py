import sys
from urllib.parse import parse_qsl, urlencode

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib import debrid, sync, wizard


def make_url(base, **params):
    return "{}?{}".format(base, urlencode(params))


def finish(handle):
    if handle >= 0:
        xbmcplugin.endOfDirectory(handle, succeeded=False)


def require_token():
    try:
        return debrid.ensure_token()
    except debrid.AuthExpired:
        if xbmcgui.Dialog().yesno("Real-Debrid", "Link your Real-Debrid account now?"):
            wizard.link_account()
            try:
                return debrid.ensure_token()
            except debrid.DebridError:
                return None
        return None
    except debrid.DebridError as error:
        xbmcgui.Dialog().ok("Real-Debrid", str(error))
        return None


def play(handle, torrent_id, file_id):
    window = xbmcgui.Window(10000)
    window.setProperty("UnknownDebrid.Playback", debrid.ADDON_ID)
    try:
        stream_url = debrid.resolve_play_url(torrent_id, file_id)
    except debrid.DebridError as error:
        window.clearProperty("UnknownDebrid.Playback")
        xbmcgui.Dialog().notification("Real-Debrid", str(error), xbmcgui.NOTIFICATION_ERROR, 6000)
        if handle >= 0:
            xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
        return
    if not stream_url or handle < 0:
        window.clearProperty("UnknownDebrid.Playback")
        if handle >= 0:
            xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
        return
    item = xbmcgui.ListItem(path=stream_url)
    item.setContentLookup(False)
    item.setProperty("IsPlayable", "true")
    xbmcplugin.setResolvedUrl(handle, True, item)


def playable_item(entry):
    if entry["kind"] == "episode":
        label = "{} S{:02d}E{:02d}".format(entry["show"], entry["season"], entry["episode"])
    else:
        label = "{} ({})".format(entry["title"], entry["year"]) if entry.get("year") else entry["title"]
    item = xbmcgui.ListItem(label, offscreen=True)
    tag = item.getVideoInfoTag()
    tag.setMediaType(entry["kind"])
    if entry["kind"] == "episode":
        tag.setTvShowTitle(entry["show"])
        tag.setSeason(int(entry["season"]))
        tag.setEpisode(int(entry["episode"]))
        tag.setTitle(label)
    else:
        tag.setTitle(entry["title"])
        if entry.get("year"):
            tag.setYear(int(entry["year"]))
    item.setProperty("IsPlayable", "true")
    return entry["play"], item, False


def root_items(base):
    addon = xbmcaddon.Addon()
    linked = bool(addon.getSetting("access_token"))
    entries = [
        (make_url(base, mode="movies"), addon.getLocalizedString(30020), True),
        (make_url(base, mode="shows"), addon.getLocalizedString(30021), True),
        (make_url(base, mode="torrents"), addon.getLocalizedString(30022), True),
        (make_url(base, action="sync"), addon.getLocalizedString(30023), False),
        (make_url(base, action="settings"), addon.getLocalizedString(30024), False),
        (make_url(base, action="auth"), addon.getLocalizedString(30026 if linked else 30025), False),
        (make_url(base, action="about"), addon.getLocalizedString(30027), False),
    ]
    items = []
    for target, label, is_folder in entries:
        item = xbmcgui.ListItem(label, offscreen=True)
        item.setArt({"icon": "DefaultVideo.png"})
        items.append((target, item, is_folder))
    return items


def build_items(base, mode, params, entries):
    items = []
    if mode == "movies":
        movies = sorted((e for e in entries if e["kind"] == "movie"), key=lambda e: e["title"].lower())
        items = [playable_item(entry) for entry in movies]
    elif mode == "shows":
        shows = {}
        for entry in entries:
            if entry["kind"] == "episode":
                shows[entry["show"]] = shows.get(entry["show"], 0) + 1
        for show in sorted(shows):
            item = xbmcgui.ListItem(show, offscreen=True)
            tag = item.getVideoInfoTag()
            tag.setMediaType("tvshow")
            tag.setTitle(show)
            item.setProperty("TotalEpisodes", str(shows[show]))
            items.append((make_url(base, mode="show", name=show), item, True))
    elif mode == "show":
        name = params.get("name", "")
        episodes = [e for e in entries if e["kind"] == "episode" and e["show"] == name]
        episodes.sort(key=lambda e: (e["season"], e["episode"]))
        items = [playable_item(entry) for entry in episodes]
    elif mode == "torrents":
        groups = {}
        for entry in entries:
            groups.setdefault((entry["torrent"], entry["torrent_name"]), []).append(entry)
        for (torrent_id, torrent_name) in sorted(groups, key=lambda k: k[1].lower()):
            item = xbmcgui.ListItem(torrent_name, offscreen=True)
            item.setArt({"icon": "DefaultFolder.png"})
            items.append((make_url(base, mode="torrent", tid=torrent_id), item, True))
    elif mode == "torrent":
        torrent_id = params.get("tid", "")
        files = [e for e in entries if e["torrent"] == torrent_id]
        files.sort(key=lambda e: e["name"].lower())
        items = [playable_item(entry) for entry in files]
    return items


def show_directory(base, handle, params):
    mode = params.get("mode")
    if mode is None:
        if not debrid.is_linked():
            wizard.link_account()
        items = root_items(base)
        xbmcplugin.addDirectoryItems(handle, items, len(items))
        xbmcplugin.endOfDirectory(handle, cacheToDisc=False)
        return
    token = require_token()
    if token is None:
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    try:
        _, desired = sync.collect(token)
    except debrid.DebridError as error:
        xbmcgui.Dialog().notification("Unknown Debrid", str(error), xbmcgui.NOTIFICATION_ERROR, 6000)
        xbmcplugin.endOfDirectory(handle, succeeded=False)
        return
    entries = list(desired.values())
    if mode == "movies":
        xbmcplugin.setContent(handle, "movies")
    elif mode == "shows":
        xbmcplugin.setContent(handle, "tvshows")
    elif mode == "show":
        xbmcplugin.setContent(handle, "episodes")
    items = build_items(base, mode, params, entries)
    xbmcplugin.addDirectoryItems(handle, items, len(items))
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


def main():
    base, handle, query = sys.argv[0], int(sys.argv[1]), sys.argv[2]
    segments = [segment for segment in base.split("/") if segment][2:]
    if segments and segments[0] == "play" and len(segments) >= 3:
        play(handle, segments[1], segments[2])
        return
    params = dict(parse_qsl(query.lstrip("?")))
    action = params.get("action")
    if action == "auth":
        wizard.link_account()
    elif action == "sync":
        sync.run_sync(interactive=True)
    elif action == "clear":
        if xbmcgui.Dialog().yesno("Unknown Debrid", "Delete all synced files and remove them from the library?"):
            sync.wipe()
            xbmcgui.Dialog().notification("Unknown Debrid", "Synced files removed",
                                          xbmcgui.NOTIFICATION_INFO, 3000)
    elif action == "settings":
        xbmcaddon.Addon().openSettings()
    elif action == "about":
        xbmcgui.Dialog().ok(
            "Unknown Debrid",
            "Nothing is downloaded to this device. Your Real-Debrid torrents are streamed directly"
            " from Real-Debrid's servers.[CR][CR]The library only holds .strm pointer files - a few"
            " dozen bytes of text - that tell Kodi where to stream from. Watch it, close it, and"
            " nothing of the video remains on your device.")
    elif action == "play":
        play(handle, params.get("tid", ""), params.get("fid", ""))
        return
    else:
        show_directory(base, handle, params)
        return
    finish(handle)


main()
