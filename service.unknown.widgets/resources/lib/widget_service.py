"""Background service for the Unknown skin.

Publishes two things on the Home window (id 10000) for the skin to read:
  Window(Home).Property(Unknown.Widgets.Token)  changes whenever the library or playback state changes.
      Skins append it to widget content paths so Kodi reloads the rows.
  Window(Home).Property(Unknown.Hero.*)          the featured banner movie, rotated on a timer.
"""
import time

import xbmc
import xbmcaddon
import xbmcgui

from resources.lib import library

HOME = xbmcgui.Window(10000)
PREFIX = "Unknown."
HERO_FIELDS = ("Active", "Title", "Tagline", "Plot", "Year", "Genre", "Rating", "Runtime", "MPAA",
               "Fanart", "Poster", "ClearLogo", "Landscape", "File", "DBID")

REFRESH_EVENTS = {
    "VideoLibrary.OnScanFinished", "VideoLibrary.OnCleanFinished",
    "VideoLibrary.OnUpdate", "VideoLibrary.OnRemove", "Player.OnStop",
}
# A library scan fires VideoLibrary.OnUpdate once per item, so wait for events to go quiet.
DEBOUNCE_SECONDS = 3


class WidgetMonitor(xbmc.Monitor):
    def __init__(self):
        super().__init__()
        self.last_event = None
        self.settings_changed = False

    def onNotification(self, sender, method, data):
        if method in REFRESH_EVENTS:
            self.last_event = time.monotonic()

    def onSettingsChanged(self):
        self.settings_changed = True


class Hero:
    def __init__(self):
        self.pool = []
        self.index = -1

    def reload(self, source):
        self.pool = library.featured(source, limit=15)
        self.index = -1
        if not self.pool:
            clear_hero()

    def advance(self):
        if not self.pool:
            return
        self.index = (self.index + 1) % len(self.pool)
        movie = self.pool[self.index]
        art = movie.get("art", {})
        runtime = int(movie.get("runtime") or 0)
        rating = float(movie.get("rating") or 0.0)
        values = {
            "Title": movie.get("title", ""),
            "Tagline": movie.get("tagline", ""),
            "Plot": movie.get("plot", ""),
            "Year": movie.get("year") or "",
            "Genre": " / ".join(movie.get("genre", [])),
            "Rating": "{:.1f}".format(rating) if rating else "",
            "Runtime": "{} min".format(runtime // 60) if runtime else "",
            "MPAA": movie.get("mpaa", ""),
            "Fanart": art.get("fanart", ""),
            "Poster": art.get("poster", ""),
            "ClearLogo": art.get("clearlogo", ""),
            "Landscape": art.get("landscape", ""),
            "File": movie.get("file", ""),
            "DBID": movie.get("movieid", ""),
        }
        for field, value in values.items():
            HOME.setProperty(PREFIX + "Hero." + field, str(value))
        HOME.setProperty(PREFIX + "Hero.Active", "true")


def clear_hero():
    for field in HERO_FIELDS:
        HOME.clearProperty(PREFIX + "Hero." + field)


def load_settings():
    # A fresh Addon instance is needed to see values changed since the last one was created.
    addon = xbmcaddon.Addon()
    return {
        "hero_interval": max(5, addon.getSettingInt("hero_interval")),
        "hero_source": addon.getSettingInt("hero_source"),
    }


def refresh(hero, settings):
    HOME.setProperty(PREFIX + "Widgets.Token", str(time.time_ns()))
    hero.reload(settings["hero_source"])
    library.log("Widgets refreshed, {} featured movies".format(len(hero.pool)), xbmc.LOGINFO)


def run():
    monitor = WidgetMonitor()
    hero = Hero()
    settings = load_settings()
    refresh(hero, settings)
    next_rotation = 0.0

    while not monitor.waitForAbort(1):
        now = time.monotonic()

        if monitor.settings_changed:
            monitor.settings_changed = False
            settings = load_settings()
            monitor.last_event = now - DEBOUNCE_SECONDS

        if (monitor.last_event is not None and now - monitor.last_event >= DEBOUNCE_SECONDS
                and not xbmc.getCondVisibility("Library.IsScanningVideo")):
            monitor.last_event = None
            refresh(hero, settings)
            next_rotation = 0.0

        # Only rotate while the home screen is showing, to spare the Fire TV Stick's CPU.
        if now >= next_rotation and xbmc.getCondVisibility("Window.IsVisible(home) + !Player.HasVideo"):
            hero.advance()
            next_rotation = now + settings["hero_interval"]

    clear_hero()
    HOME.clearProperty(PREFIX + "Widgets.Token")
