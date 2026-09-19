import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import xbmc
import xbmcaddon

ADDON_ID = "plugin.video.unknown.debrid"
API = "https://api.real-debrid.com/rest/1.0"
OAUTH = "https://api.real-debrid.com/oauth/v2"
CLIENT_ID = "X245A4XAIBGVM"
GRANT = "http://oauth.net/grant_type/device/1.0"


class DebridError(Exception):
    pass


class AuthExpired(DebridError):
    pass


class AuthorizationPending(DebridError):
    pass


def log(message, level=xbmc.LOGDEBUG):
    xbmc.log("[{}] {}".format(ADDON_ID, message), level)


def _http(method, url, token=None, data=None):
    headers = {"Accept": "application/json", "User-Agent": "UnknownDebrid/1.1 Kodi/20"}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = None
    if data is not None:
        body = urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read()
    except HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        if error.code == 401:
            raise AuthExpired(detail)
        if error.code == 403 and "credentials" in url:
            raise AuthorizationPending(detail)
        raise DebridError("HTTP {} from {}: {}".format(error.code, url, detail))
    except URLError as error:
        raise DebridError("Cannot reach Real-Debrid: {}".format(error))
    return json.loads(payload) if payload else {}


def device_start():
    url = "{}/device/code?client_id={}&new_credentials=yes".format(OAUTH, CLIENT_ID)
    try:
        device = _http("GET", url)
    except DebridError as error:
        log("device/code over GET failed ({}), retrying as POST".format(error), xbmc.LOGINFO)
        device = _http("POST", url)
    if not device.get("device_code") or not device.get("user_code"):
        raise DebridError("Unexpected reply from Real-Debrid: {}".format(device))
    return device


def device_credentials(device_code):
    return _http("GET", "{}/device/credentials?client_id={}&code={}".format(OAUTH, CLIENT_ID, device_code))


def device_token(client_id, client_secret, code):
    return _http("POST", OAUTH + "/token", data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": GRANT,
    })


def store_auth(access_token, refresh_token, expires_in, client_id="", client_secret=""):
    addon = xbmcaddon.Addon()
    addon.setSetting("access_token", access_token)
    addon.setSetting("refresh_token", refresh_token)
    addon.setSetting("token_expires", str(int(time.time()) + int(expires_in)))
    addon.setSetting("client_id", client_id)
    addon.setSetting("client_secret", client_secret)


def clear_auth():
    addon = xbmcaddon.Addon()
    for key in ("access_token", "refresh_token", "token_expires", "client_id", "client_secret"):
        addon.setSetting(key, "")


def is_linked():
    addon = xbmcaddon.Addon()
    return bool(addon.getSetting("api_token").strip() or addon.getSetting("access_token"))


def ensure_token():
    addon = xbmcaddon.Addon()
    private = addon.getSetting("api_token").strip()
    if private:
        return private
    token = addon.getSetting("access_token")
    if not token:
        raise AuthExpired("No Real-Debrid account linked")
    if int(time.time()) < int(addon.getSetting("token_expires") or 0) - 60:
        return token
    client_id = addon.getSetting("client_id")
    client_secret = addon.getSetting("client_secret")
    refresh_token = addon.getSetting("refresh_token")
    if not client_id or not refresh_token:
        raise AuthExpired("Stored authorization is incomplete")
    refreshed = device_token(client_id, client_secret, refresh_token)
    store_auth(refreshed["access_token"], refreshed["refresh_token"], refreshed["expires_in"],
               client_id, client_secret)
    return refreshed["access_token"]


def user(token):
    return _http("GET", API + "/user", token)


def torrents(token):
    results, page = [], 1
    while True:
        batch = _http("GET", "{}/torrents?page={}&limit=100".format(API, page), token)
        if not batch:
            return results
        results.extend(batch)
        if len(batch) < 100:
            return results
        page += 1


def torrent_info(token, torrent_id):
    return _http("GET", "{}/torrents/info/{}".format(API, torrent_id), token)


def unrestrict(token, link):
    return _http("POST", API + "/unrestrict/link", token, data={"link": link})


def resolve_play_url(torrent_id, file_id):
    token = ensure_token()
    info = torrent_info(token, torrent_id)
    selected = [entry for entry in info.get("files", []) if entry.get("selected")]
    links = info.get("links", [])
    index = next((i for i, entry in enumerate(selected) if str(entry.get("id")) == str(file_id)), None)
    if index is None or index >= len(links):
        raise DebridError("File {} is no longer available in torrent {}".format(file_id, torrent_id))
    return unrestrict(token, links[index]).get("download", "")
