import sys
from urllib.parse import parse_qsl, urlencode

import xbmcaddon
import xbmcgui
import xbmcplugin

from resources.lib import library, listitems

# list name -> (label string id, container content type, fetch function)
WIDGETS = {
    "continue": (30100, "videos", lambda addon: library.in_progress(
        addon.getSettingInt("widget_limit"))),
    "recent": (30101, "videos", lambda addon: library.recently_added(
        addon.getSettingInt("widget_limit"), addon.getSettingBool("hide_watched_recent"))),
    "random": (30102, "videos", lambda addon: library.random_picks(
        addon.getSettingInt("widget_limit"))),
    "featured": (30103, "movies", lambda addon: library.featured(
        addon.getSettingInt("hero_source"), addon.getSettingInt("widget_limit"))),
}


def list_widgets(base_url, addon):
    """Root menu, so the widgets can be browsed from Video add-ons for testing."""
    items = []
    for name, (label_id, _, _) in WIDGETS.items():
        url = "{}?{}".format(base_url, urlencode({"list": name}))
        items.append((url, xbmcgui.ListItem(addon.getLocalizedString(label_id), offscreen=True), True))
    return items


def show_info(dbid):
    """Open Kodi's info dialog for a library movie; the skin's "More info" button calls this via RunPlugin."""
    movie = library.movie_details(dbid)
    if movie:
        url, li, _ = listitems.build(movie)
        li.setPath(url)
        xbmcgui.Dialog().info(li)


def main():
    base_url, handle, query = sys.argv[0], int(sys.argv[1]), sys.argv[2]
    params = dict(parse_qsl(query.lstrip("?")))
    if params.get("action") == "info":
        show_info(int(params.get("dbid") or 0))
        return
    addon = xbmcaddon.Addon()

    widget = WIDGETS.get(params.get("list"))
    if widget is None:
        items = list_widgets(base_url, addon)
    else:
        _, content, fetch = widget
        items = [listitems.build(item) for item in fetch(addon)]
        xbmcplugin.setContent(handle, content)

    xbmcplugin.addDirectoryItems(handle, items, len(items))
    xbmcplugin.endOfDirectory(handle, cacheToDisc=False)


main()
