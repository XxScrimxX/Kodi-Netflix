"""Video library queries for the Unknown widgets, via Kodi's JSON-RPC API.

Kodi 20 on Android ships Python 3.8, so avoid newer syntax (dict |, str.removeprefix, list[int] hints).
"""
import json
import random

import xbmc

ADDON_ID = "service.unknown.widgets"

MOVIE_PROPERTIES = [
    "title", "year", "plot", "tagline", "genre", "rating", "runtime", "mpaa",
    "file", "art", "playcount", "resume", "dateadded", "lastplayed",
]
EPISODE_PROPERTIES = [
    "title", "showtitle", "tvshowid", "season", "episode", "plot", "rating", "runtime",
    "firstaired", "file", "art", "playcount", "resume", "dateadded", "lastplayed",
]
TVSHOW_PROPERTIES = [
    "title", "year", "plot", "genre", "rating", "mpaa", "file", "art",
    "episode", "watchedepisodes", "dateadded",
]

IN_PROGRESS = {"field": "inprogress", "operator": "true", "value": ""}
UNWATCHED = {"field": "playcount", "operator": "is", "value": "0"}

# hero_source setting values
FEATURED_RANDOM_UNWATCHED = 0
FEATURED_RECENTLY_ADDED = 1
FEATURED_IN_PROGRESS = 2


def log(message, level=xbmc.LOGDEBUG):
    xbmc.log("[{}] {}".format(ADDON_ID, message), level)


def rpc(method, **params):
    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    response = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
    if "error" in response:
        log("{} failed: {}".format(method, response["error"]), xbmc.LOGWARNING)
        return {}
    return response.get("result", {})


def _query(media_type, properties, limit, sort, filter_=None):
    """Fetch movies, episodes or tvshows, tagging each result with its media type."""
    method = {"movie": "VideoLibrary.GetMovies",
              "episode": "VideoLibrary.GetEpisodes",
              "tvshow": "VideoLibrary.GetTVShows"}[media_type]
    params = {"properties": properties, "limits": {"start": 0, "end": limit}, "sort": sort}
    if filter_:
        params["filter"] = filter_
    items = rpc(method, **params).get(media_type + "s", [])
    for item in items:
        item["type"] = media_type
    return items


def _one_episode_per_show(items):
    """Keep only the first episode of each show, so a row doesn't repeat the same show poster."""
    seen_shows = set()
    result = []
    for item in items:
        if item["type"] == "episode":
            if item.get("tvshowid") in seen_shows:
                continue
            seen_shows.add(item.get("tvshowid"))
        result.append(item)
    return result


def in_progress(limit):
    """Partially watched movies and episodes, most recently played first."""
    sort = {"method": "lastplayed", "order": "descending"}
    # Over-fetch episodes, since several may collapse into one entry per show.
    items = (_query("movie", MOVIE_PROPERTIES, limit, sort, IN_PROGRESS)
             + _query("episode", EPISODE_PROPERTIES, limit * 4, sort, IN_PROGRESS))
    items.sort(key=lambda item: item.get("lastplayed", ""), reverse=True)
    return _one_episode_per_show(items)[:limit]


def recently_added(limit, hide_watched=False):
    """Newest movies and episodes, newest first, one episode per show."""
    sort = {"method": "dateadded", "order": "descending"}
    filter_ = UNWATCHED if hide_watched else None
    items = (_query("movie", MOVIE_PROPERTIES, limit, sort, filter_)
             + _query("episode", EPISODE_PROPERTIES, limit * 4, sort, filter_))
    items.sort(key=lambda item: item.get("dateadded", ""), reverse=True)
    return _one_episode_per_show(items)[:limit]


def random_picks(limit):
    """A shuffled mix of unwatched movies and TV shows."""
    sort = {"method": "random"}
    items = (_query("movie", MOVIE_PROPERTIES, limit, sort, UNWATCHED)
             + _query("tvshow", TVSHOW_PROPERTIES, limit, sort, UNWATCHED))
    random.shuffle(items)
    return items[:limit]


def featured(source, limit):
    """Movies for the featured banner. Only movies with fanart qualify, since the banner needs a backdrop."""
    if source == FEATURED_RECENTLY_ADDED:
        sort, filter_ = {"method": "dateadded", "order": "descending"}, None
    elif source == FEATURED_IN_PROGRESS:
        sort, filter_ = {"method": "lastplayed", "order": "descending"}, IN_PROGRESS
    else:
        sort, filter_ = {"method": "random"}, UNWATCHED
    # Over-fetch so that skipping movies without fanart still fills the pool.
    movies = _query("movie", MOVIE_PROPERTIES, limit * 2, sort, filter_)
    return [movie for movie in movies if movie.get("art", {}).get("fanart")][:limit]


def movie_details(movie_id):
    movie = rpc("VideoLibrary.GetMovieDetails", movieid=movie_id, properties=MOVIE_PROPERTIES).get("moviedetails")
    if movie:
        movie["type"] = "movie"
    return movie
