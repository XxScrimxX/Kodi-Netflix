"""Build a placeholder Kodi video library from TMDb, for testing the Unknown skin on a PC.

For each title it writes an empty video file next to a full .nfo (title, plot, genres, poster,
fanart, clearlogo). Scanned with Kodi's "Local information only" scraper, the library fills with
real artwork and descriptions. The video files are empty, so nothing will actually play.

Usage:
    py tools/make_test_library.py --key-file PATH [--movies 40] [--shows 12] [--episodes 4] [--clean]

The key can also come from the TMDB_API_KEY environment variable. Keep the key out of this project.
"""
import argparse
import json
import os
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_URL = "https://api.themoviedb.org/3"
IMAGE_URL = "https://image.tmdb.org/t/p/"
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "test-library"
# News, Reality and Talk shows rarely have useful season data or artwork.
SKIPPED_TV_GENRES = {10763, 10764, 10767}


class Tmdb:
    def __init__(self, key):
        self.key = key.strip()

    def get(self, path, **params):
        headers = {"Accept": "application/json"}
        if self.key.startswith("eyJ"):  # v4 "API Read Access Token"
            headers["Authorization"] = "Bearer " + self.key
        else:  # v3 "API Key"
            params["api_key"] = self.key
        request = Request("{}{}?{}".format(API_URL, path, urlencode(params)), headers=headers)
        for attempt in range(4):
            try:
                with urlopen(request, timeout=30) as response:
                    return json.load(response)
            except HTTPError as error:
                if error.code == 401:
                    sys.exit("TMDb rejected the key (HTTP 401). Use a v3 API key or a v4 API read access token.")
                if error.code == 404:
                    return None
                if error.code == 429 and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise
        return None

    def popular(self, kind, count, keep):
        """Up to `count` popular movies or TV shows that pass `keep`."""
        seen, results = set(), []
        for page in range(1, 21):
            data = self.get("/{}/popular".format(kind), page=page, language="en-US") or {}
            for item in data.get("results", []):
                if item["id"] not in seen and keep(item):
                    seen.add(item["id"])
                    results.append(item)
            if len(results) >= count or page >= data.get("total_pages", 0):
                break
        return results[:count]


def image(path, size):
    return IMAGE_URL + size + path if path else None


def best_logo(images):
    # Kodi cannot draw SVG, so only PNG logos qualify.
    logos = [logo for logo in (images or {}).get("logos", [])
             if logo.get("iso_639_1") in ("en", None) and logo.get("file_path", "").endswith(".png")]
    logos.sort(key=lambda logo: logo.get("vote_average", 0), reverse=True)
    return logos[0]["file_path"] if logos else None


def safe_name(text):
    return re.sub(r'[<>:"/\\|?*]', "", text).strip().rstrip(".")


def add(parent, tag, value, **attrs):
    if value in (None, "", []):
        return None
    element = ET.SubElement(parent, tag, attrs)
    element.text = str(value)
    return element


def add_rating(parent, average, votes):
    if not average:
        return
    rating = ET.SubElement(ET.SubElement(parent, "ratings"), "rating", name="themoviedb", max="10", default="true")
    add(rating, "value", round(average, 1))
    add(rating, "votes", votes)


def add_art(parent, poster, fanart, logo):
    add(parent, "thumb", image(poster, "w500"), aspect="poster")
    add(parent, "thumb", image(logo, "w500"), aspect="clearlogo")
    if fanart:
        add(ET.SubElement(parent, "fanart"), "thumb", image(fanart, "w1280"))


def write_nfo(root, path):
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="UTF-8", xml_declaration=True)


def us_certification(details, key, list_key, value_key):
    for country in details.get(key, {}).get("results", []):
        if country.get("iso_3166_1") != "US":
            continue
        entries = country.get(list_key, [country]) if list_key else [country]
        for entry in entries:
            if entry.get(value_key):
                return "Rated " + entry[value_key]
    return None


def build_movie(tmdb, summary, movies_dir):
    details = tmdb.get("/movie/{}".format(summary["id"]), language="en-US",
                       append_to_response="images,release_dates", include_image_language="en,null")
    if not details or not details.get("release_date"):
        return None
    name = safe_name("{} ({})".format(details["title"], details["release_date"][:4]))
    folder = movies_dir / name
    folder.mkdir(parents=True, exist_ok=True)

    nfo = ET.Element("movie")
    add(nfo, "title", details["title"])
    if details.get("original_title") != details["title"]:
        add(nfo, "originaltitle", details.get("original_title"))
    add(nfo, "tagline", details.get("tagline"))
    add(nfo, "plot", details.get("overview"))
    add(nfo, "runtime", details.get("runtime"))
    add(nfo, "premiered", details["release_date"])
    add(nfo, "mpaa", us_certification(details, "release_dates", "release_dates", "certification"))
    for genre in details.get("genres", []):
        add(nfo, "genre", genre["name"])
    for company in details.get("production_companies", [])[:2]:
        add(nfo, "studio", company["name"])
    add_rating(nfo, details.get("vote_average"), details.get("vote_count"))
    add(nfo, "uniqueid", details["id"], type="tmdb", default="true")
    add(nfo, "uniqueid", details.get("imdb_id"), type="imdb")
    add_art(nfo, details.get("poster_path"), details.get("backdrop_path"), best_logo(details.get("images")))

    write_nfo(nfo, folder / (name + ".nfo"))
    (folder / (name + ".mkv")).touch()
    return name


def build_show(tmdb, summary, shows_dir, episode_count):
    details = tmdb.get("/tv/{}".format(summary["id"]), language="en-US",
                       append_to_response="images,content_ratings", include_image_language="en,null")
    if not details or not details.get("first_air_date"):
        return None
    season = tmdb.get("/tv/{}/season/1".format(summary["id"]), language="en-US") or {}
    episodes = [episode for episode in season.get("episodes", []) if episode.get("episode_number")][:episode_count]
    if not episodes:
        return None

    title = safe_name(details["name"])
    name = safe_name("{} ({})".format(details["name"], details["first_air_date"][:4]))
    season_dir = shows_dir / name / "Season 01"
    season_dir.mkdir(parents=True, exist_ok=True)

    nfo = ET.Element("tvshow")
    add(nfo, "title", details["name"])
    add(nfo, "plot", details.get("overview"))
    add(nfo, "premiered", details["first_air_date"])
    add(nfo, "mpaa", us_certification(details, "content_ratings", None, "rating"))
    for genre in details.get("genres", []):
        add(nfo, "genre", genre["name"])
    for network in details.get("networks", [])[:1]:
        add(nfo, "studio", network["name"])
    add_rating(nfo, details.get("vote_average"), details.get("vote_count"))
    add(nfo, "uniqueid", details["id"], type="tmdb", default="true")
    add_art(nfo, details.get("poster_path"), details.get("backdrop_path"), best_logo(details.get("images")))
    add(nfo, "thumb", image(season.get("poster_path"), "w500"), aspect="poster", type="season", season="1")
    write_nfo(nfo, shows_dir / name / "tvshow.nfo")

    for episode in episodes:
        base = "{} S01E{:02d}".format(title, episode["episode_number"])
        episode_nfo = ET.Element("episodedetails")
        add(episode_nfo, "title", episode.get("name"))
        add(episode_nfo, "showtitle", details["name"])
        add(episode_nfo, "season", 1)
        add(episode_nfo, "episode", episode["episode_number"])
        add(episode_nfo, "plot", episode.get("overview"))
        add(episode_nfo, "aired", episode.get("air_date"))
        add(episode_nfo, "runtime", episode.get("runtime"))
        add(episode_nfo, "thumb", image(episode.get("still_path"), "w300"))
        add_rating(episode_nfo, episode.get("vote_average"), episode.get("vote_count"))
        write_nfo(episode_nfo, season_dir / (base + ".nfo"))
        (season_dir / (base + ".mkv")).touch()
    return name


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Build a placeholder Kodi library from TMDb.")
    parser.add_argument("--key-file", type=Path, help="file containing a TMDb v3 API key or v4 read access token")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--movies", type=int, default=40)
    parser.add_argument("--shows", type=int, default=12)
    parser.add_argument("--episodes", type=int, default=4, help="episodes per show (season 1)")
    parser.add_argument("--clean", action="store_true", help="delete previously generated Movies and TV Shows first")
    args = parser.parse_args()

    key = args.key_file.read_text(encoding="utf-8") if args.key_file else os.environ.get("TMDB_API_KEY", "")
    if not key.strip():
        sys.exit("No TMDb key: pass --key-file or set TMDB_API_KEY.")
    tmdb = Tmdb(key)

    movies_dir, shows_dir = args.output / "Movies", args.output / "TV Shows"
    if args.clean:
        for folder in (movies_dir, shows_dir):
            if folder.exists():
                shutil.rmtree(folder)

    movies = 0
    candidates = tmdb.popular("movie", args.movies + 10,
                              lambda item: item.get("poster_path") and item.get("backdrop_path"))
    for summary in candidates:
        if movies >= args.movies:
            break
        name = build_movie(tmdb, summary, movies_dir)
        if name:
            movies += 1
            print("movie  ", name)

    shows = 0
    candidates = tmdb.popular("tv", args.shows + 10, lambda item: item.get("poster_path") and item.get("backdrop_path")
                              and not SKIPPED_TV_GENRES.intersection(item.get("genre_ids", [])))
    for summary in candidates:
        if shows >= args.shows:
            break
        name = build_show(tmdb, summary, shows_dir, args.episodes)
        if name:
            shows += 1
            print("tvshow ", name)

    print("\n{} movies in {}\n{} TV shows in {}".format(movies, movies_dir, shows, shows_dir))


if __name__ == "__main__":
    main()
