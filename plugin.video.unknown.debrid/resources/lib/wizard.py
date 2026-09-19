import time

import xbmcgui

from resources.lib import debrid, sync


def link_account():
    try:
        device = debrid.device_start()
    except debrid.DebridError as error:
        xbmcgui.Dialog().ok("Unknown Debrid", "Could not reach Real-Debrid:[CR]{}".format(error))
        return False
    verification = device.get("verification_url", "https://real-debrid.com/device")
    code = device.get("user_code", "")
    dialog = xbmcgui.DialogProgress()
    dialog.create(
        "Link your Real-Debrid account",
        "[B]Step 1[/B]  On your phone or computer, open:[CR][B]{}[/B][CR][CR]"
        "[B]Step 2[/B]  Type in this code:[CR][B]{}[/B][CR][CR]"
        "This window closes by itself once you're linked.".format(verification, code))
    interval = max(2, int(device.get("interval", 5)))
    deadline = time.time() + int(device.get("expires_in", 600))
    while time.time() < deadline:
        if dialog.iscanceled():
            dialog.close()
            return False
        try:
            credentials = debrid.device_credentials(device["device_code"])
        except debrid.AuthorizationPending:
            time.sleep(interval)
            continue
        except debrid.DebridError as error:
            dialog.close()
            xbmcgui.Dialog().ok("Unknown Debrid", "Authorization failed:[CR]{}".format(error))
            return False
        try:
            tokens = debrid.device_token(credentials["client_id"], credentials["client_secret"],
                                         device["device_code"])
        except debrid.DebridError as error:
            dialog.close()
            xbmcgui.Dialog().ok("Unknown Debrid", "Could not finish linking:[CR]{}".format(error))
            return False
        debrid.store_auth(tokens["access_token"], tokens["refresh_token"], tokens["expires_in"],
                          credentials["client_id"], credentials["client_secret"])
        try:
            account = debrid.user(tokens["access_token"])
            greeting = "Linked as {}".format(account.get("username", "your account"))
        except debrid.DebridError:
            greeting = "Account linked"
        dialog.close()
        xbmcgui.Dialog().notification("Real-Debrid", greeting, xbmcgui.NOTIFICATION_INFO, 4000)
        sync.run_sync(interactive=True)
        return True
    dialog.close()
    xbmcgui.Dialog().ok("Unknown Debrid", "Linking timed out. Open Unknown Debrid to try again.")
    return False
