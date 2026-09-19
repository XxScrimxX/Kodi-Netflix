"""Serve repo/ over HTTP so Kodi on the Fire TV Stick can install and update the Unknown add-ons.

Started in the background at Windows login by the "Unknown Kodi Repository" scheduled task, through
tools/start_repo_server.vbs (python.exe in a hidden window). Requests are logged to repo-server.log in the project root.
"""
import functools
import http.server
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO_DIR = ROOT / "repo"
PORT = 8000


class RepoHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Kodi must always see the latest addons.xml, or Update won't find new versions.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format, *args):
        # The console window is hidden, so log to a file instead of stderr.
        logging.info("%s %s [%s]", self.address_string(), format % args, self.headers.get("User-Agent", "-"))


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        handlers=[RotatingFileHandler(ROOT / "repo-server.log", maxBytes=1_000_000, backupCount=1)])
    REPO_DIR.mkdir(exist_ok=True)
    handler = functools.partial(RepoHandler, directory=str(REPO_DIR))
    with http.server.ThreadingHTTPServer(("", PORT), handler) as server:
        logging.info("Serving %s on port %d", REPO_DIR, PORT)
        server.serve_forever()


if __name__ == "__main__":
    main()
