import os
import re

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".m4v", ".avi", ".ts", ".m2ts", ".wmv", ".mov", ".mpg", ".mpeg", ".flv", ".webm"}

EPISODE_PATTERNS = [
    re.compile(r"[sS](\d{1,2})[eE](\d{1,3})"),
    re.compile(r"(\d{1,2})x(\d{1,3})"),
]
YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")
JUNK_PATTERN = re.compile(
    r"\b(2160p|1080p|720p|480p|576p|4k|uhd|hdr10\+?|hdr|dv|10bit|8bit|"
    r"blu-?ray|bdrip|brrip|remux|web-?dl|webrip|hdtv|hdrip|dvdrip|dvdscr|"
    r"x264|x265|h\.?264|h\.?265|hevc|avc|xvid|divx|"
    r"aac|ac3|eac3|ddp?5\.1|dts(?:-?hd)?|truehd|atmos|flac|mp3|2\.0|5\.1|7\.1|"
    r"proper|repack|internal|limited|extended|unrated|theatrical|remastered|"
    r"multi|dual|dubbed|subbed|complete|imax|nf|amzn|hulu|dsnp|atvp|hmax|pcok)\b",
    re.IGNORECASE,
)
SAMPLE_PATTERN = re.compile(r"\bsample\b", re.IGNORECASE)


def is_video(path):
    return os.path.splitext(path)[1].lower() in VIDEO_EXTENSIONS


def is_sample(path):
    return bool(SAMPLE_PATTERN.search(os.path.basename(path)))


def safe_name(text):
    return re.sub(r'[<>:"/\\|?*]', "", text).strip().rstrip(".")


def clean_title(text):
    text = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", text)
    text = text.replace(".", " ").replace("_", " ").replace("-", " ")
    text = re.sub(r"[\[\]{}()]", " ", text)
    text = JUNK_PATTERN.sub(" ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" -")


def parse(path, torrent_name=""):
    base = os.path.basename(path)
    for pattern in EPISODE_PATTERNS:
        match = pattern.search(base)
        if match:
            show = clean_title(base[:match.start()])
            if not show and torrent_name:
                show = clean_title(pattern.split(torrent_name)[0])
            if not show:
                show = clean_title(os.path.basename(os.path.dirname(path)))
            return {"kind": "episode", "show": show or "Unknown Show",
                    "season": int(match.group(1)), "episode": int(match.group(2))}
    year_match = YEAR_PATTERN.search(base)
    year = int(year_match.group(1)) if year_match else None
    title = clean_title(base[:year_match.start()] if year_match else base)
    if not title and torrent_name:
        torrent_year = YEAR_PATTERN.search(torrent_name)
        title = clean_title(torrent_name[:torrent_year.start()] if torrent_year else torrent_name)
        if year is None and torrent_year:
            year = int(torrent_year.group(1))
    return {"kind": "movie", "title": title or "Unknown Movie", "year": year}
