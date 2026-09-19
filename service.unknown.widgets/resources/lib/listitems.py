"""Turn library query results into ListItems that behave like native library items."""
import xbmcgui


def build(item):
    """Return a (url, ListItem, is_folder) tuple for xbmcplugin.addDirectoryItems."""
    return {"movie": _movie, "episode": _episode, "tvshow": _tvshow}[item["type"]](item)


def _base(item, media_type, dbid):
    li = xbmcgui.ListItem(item.get("title") or item.get("label", ""), offscreen=True)
    tag = li.getVideoInfoTag()
    tag.setMediaType(media_type)
    tag.setDbId(dbid)
    tag.setTitle(item.get("title", ""))
    tag.setPlot(item.get("plot", ""))
    tag.setRating(float(item.get("rating") or 0.0))
    if item.get("dateadded"):
        tag.setDateAdded(item["dateadded"])
    return li, tag


def _playable(item, tag):
    """Fields that let Kodi track watched status and offer resume for playable items."""
    tag.setDuration(int(item.get("runtime") or 0))
    tag.setPlaycount(int(item.get("playcount") or 0))
    tag.setFilenameAndPath(item.get("file", ""))
    if item.get("lastplayed"):
        tag.setLastPlayed(item["lastplayed"])
    resume = item.get("resume") or {}
    if resume.get("position"):
        tag.setResumePoint(resume["position"], resume.get("total") or 0)


def _movie(item):
    li, tag = _base(item, "movie", item["movieid"])
    _playable(item, tag)
    tag.setYear(int(item.get("year") or 0))
    tag.setGenres(item.get("genre", []))
    tag.setTagLine(item.get("tagline", ""))
    tag.setMpaa(item.get("mpaa", ""))
    li.setArt(item.get("art", {}))
    return item["file"], li, False


def _episode(item):
    li, tag = _base(item, "episode", item["episodeid"])
    _playable(item, tag)
    tag.setTvShowTitle(item.get("showtitle", ""))
    tag.setSeason(int(item.get("season") or 0))
    tag.setEpisode(int(item.get("episode") or 0))
    if item.get("firstaired"):
        tag.setFirstAired(item["firstaired"])
    art = dict(item.get("art", {}))
    # Poster rows expect poster/fanart; episodes only carry them under the show's prefix.
    art.setdefault("poster", art.get("tvshow.poster", art.get("season.poster", "")))
    art.setdefault("fanart", art.get("tvshow.fanart", ""))
    li.setArt(art)
    return item["file"], li, False


def _tvshow(item):
    li, tag = _base(item, "tvshow", item["tvshowid"])
    tag.setYear(int(item.get("year") or 0))
    tag.setGenres(item.get("genre", []))
    tag.setMpaa(item.get("mpaa", ""))
    total = int(item.get("episode") or 0)
    watched = int(item.get("watchedepisodes") or 0)
    li.setProperty("TotalEpisodes", str(total))
    li.setProperty("WatchedEpisodes", str(watched))
    li.setProperty("UnWatchedEpisodes", str(total - watched))
    li.setArt(item.get("art", {}))
    return "videodb://tvshows/titles/{}/".format(item["tvshowid"]), li, True
