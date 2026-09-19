# Unknown

A Netflix-style home screen for Kodi, built on Estuary, with a Real-Debrid streaming pipeline.

Your Kodi home becomes a streaming box: **Continue Watching**, **Recently Added**, **Random Picks** and a rotating hero banner — all fed by your **Real-Debrid account**. Torrents you add to Real-Debrid appear in your library; torrents you remove disappear. Nothing is ever downloaded to your device: the library holds only tiny `.strm` pointer files and the video streams directly from Real-Debrid's servers.

> **Target hardware:** Amazon Fire TV Stick (D-pad remote, low-memory). Works on any Kodi 20 device.

---

## Features

- **Netflix-style home screen** with rotating hero banner, poster rows and D-pad-first navigation.
- **Real-Debrid sync engine** — your torrents become a proper Kodi video library:
  - Movies and TV shows scraped with TMDb metadata (artwork, plots, ratings).
  - Single episodes, whole seasons, whole shows, whole torrents — everything.
  - **Recently Added** reflects the *Real-Debrid added timestamp*, not the local scan time.
- **Automatic source registration** — the addon registers its own video sources, no manual library setup.
- **One-time device-flow linking** — a startup wizard gives you a code, you confirm on real-debrid.com, done. Private API token entry also supported.
- **Full streaming** — playback resolves fresh links from Real-Debrid per play; the device stores nothing but pointers.
- **Audio forcing** — multi-language torrents (e.g. Russian releases with an English track) automatically switch to English on playback.
- **Two-way sync** — remove a torrent or season on Real-Debrid and it leaves your library on the next sync.
- **First-use wizard** — boots with Kodi, links your account, runs the first sync, all unattended.

## What's in the repo

| Addon | Purpose |
|---|---|
| `skin.unknown` | Netflix-style skin. Estuary fork, GPL-2.0. |
| `service.unknown.widgets` | Background service that publishes hero rotation and refreshes the home rows on library/playback changes. |
| `plugin.video.unknown.debrid` | Real-Debrid client: device-flow auth, sync engine, library source registration, playback resolution, English-audio forcing, startup wizard. |
| `tools/` | Dev utilities — zip builder, TMDb test-library generator, PC-only cleanup scripts. |

## Requirements

- **Kodi 20.5 "Nexus"** (Python 3.8) — Android / Fire TV Stick / Windows / Linux / macOS.
- A **Real-Debrid account** (paid). Free accounts won't work (no usable streams after the free trial).
- Torrents you want to watch must be **finished downloading on Real-Debrid's servers** (`status: downloaded`) — the addon only syncs finished torrents, since only those are streamable.

## Installation

**Option A — via the repository addon (recommended, self-updating):**

1. Download `repository.unknown-X.Y.Z.zip` from **Releases**.
2. In Kodi: **Settings → Add-ons → Install from zip file** → pick the repository zip.
3. Kodi offers the Unknown add-on set from the repository → install *Unknown Debrid* (plugin), *Unknown Widgets* (service), *Unknown* (skin).
4. **Settings → Interface → Skin → Unknown**, restart Kodi.

Updates are then delivered automatically from the repository — **no configuration, no home network, no IP addresses anywhere**. The repository is hosted on GitHub Pages (a static URL that works for every device on earth); your PC doesn't even need to be on.

**Option B — direct zips (manual):**

1. Download the three addon zips (from **Releases**, or build them yourself — see [Development](#development)):
   - `plugin.video.unknown.debrid-X.Y.Z.zip`
   - `service.unknown.widgets-X.Y.Z.zip`
   - `skin.unknown-X.Y.Z.zip`
2. In Kodi: **Settings → Add-ons → Install from zip file** → install in this order:
   1. `plugin.video.unknown.debrid` *(plugin — must exist before the skin's rows can stream)*
   2. `service.unknown.widgets` *(service — feeds the home rows)*
   3. `skin.unknown` *(the skin itself — install last)*
3. **Settings → Interface → Skin → Unknown**.
4. Restart Kodi.

> **Fire TV Stick note (Option B only):** when installing the zips directly, files over the network can be grabbed with the *Downloader* app (direct file URLs) or through Kodi's file manager. First sideload/third-party install requires *Settings → My Fire TV → Developer options → Install unknown apps → allow Downloader*.

## First run

On the first boot after installing, the **wizard** appears automatically:

1. It shows a URL and a code.
2. Open the URL on any device (phone/PC): `https://real-debrid.com/device`.
3. Enter the code, log in, confirm.
4. The addon finishes linking, syncs your torrents, registers its library sources, and scans.

The wizard is also reachable anytime: open the addon, or **Add-ons → Unknown Debrid → settings → "Link Real-Debrid account"**.

**Alternative:** paste a private API token from `real-debrid.com/apitoken` into *Unknown Debrid settings → Private API token (advanced)* — skips the device flow entirely.

## How it works

```
 Real-Debrid                      Your device (Kodi)
 ────────────                      ─────────────────
 RD servers ──finished torrent──► sync engine reads torrent list
                                   │                          │
                                   │ writes .strm pointers    │ registers video
                                   │ (57 bytes each: the      │ sources + kicks
                                   │  plugin:// play URL)     │ scan
                                   ▼                          ▼
                                library/  ──────────────►  Kodi library with
                                *.strm                   TMDb artwork & dates
                                   │
 play: Kodi opens the .strm ───────┘
        → plugin resolves a fresh
          https link from RD
        → video streams RD → Kodi
          memory → screen
        → nothing is saved
```

- **Net storage on device:** ~60 bytes per title (the pointer). A 30 GB season = ~5 KB on disk.
- **No caching of the video:** playback streams over HTTPS and forgets.
- **Resume points / watched state:** regular Kodi state, stored in Kodi's own library database — which makes Continue Watching real.
- **Recently Added order:** the sync writes the torrent's Real-Debrid `added` timestamp into Kodi's `dateAdded` after each scan.
- **Removals:** each sync diffs the current RD torrent list against the last sync's manifest; gone torrents/seasons delete their `.strm` files, then a library clean removes the entries.

## Home screen rows

| Row | Source |
|---|---|
| Hero banner | Random unwatched, recently added, or in-progress movies (selectable) |
| Continue Watching | Real resume points, most recently played first, one entry per show |
| Recently Added | Newest by Real-Debrid added date, one episode per show |
| Random Picks | Shuffled mix of unwatched movies **and** TV shows (limit configurable) |

Row limits in *service.unknown.widgets* settings; hero behaviour likewise. The rows reload automatically whenever the library or playback state changes.

## Real-Debrid usage

- Add torrents/magnets at real-debrid.com (or any RD client).
- Wait for them to finish downloading (**downloaded** status) — the addon will pick them up on the next sync:
  - at Kodi startup,
  - every **sync interval** (default 15 min),
  - or immediately via **Unknown Debrid → settings → "Sync library now"**.
- Remove stuff on RD and it disappears from Kodi on the next sync, library-clean included.
- Currently **downloading** torrents are intentionally not synced (nothing to stream yet). The sync dialog reports exactly what it found: *"6 torrents, 2 finished, statuses: 4 downloading"*.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "unable to link" / auth fails in wizard | Device flow returned no code. Update the addon; or paste a private API token from `real-debrid.com/apitoken` into settings. |
| Sync says "0 new" | Torrent status is not `downloaded` (still downloading / awaiting file selection). Check real-debrid.com. The sync dialog now states statuses explicitly. |
| Russian / wrong audio | Torrent has multiple audio tracks and the non-English one is flagged default. The addon auto-switches to English on playback (toggle: *Force English audio track*). |
| Library empty after sync | The scan fires after sources are registered; give it time, or press **Sync now**. Log line `ensure_sources: N target(s), db_ok=..., added=...` tells you what happened. |
| "Couldn't retrieve directory information" on the stick | Only affects LAN installs/publishing: the HTTP server isn't running or the firewall blocks it. Use `publish-update.bat --lan` (auto-detects this PC's IP), keep the server window open, allow Python through Windows Firewall. The GitHub Pages repository (Option A) never hits this — it's a public URL on the internet. |
| Stale/placeholder content on a dev PC | That PC had a generated test library. Run `tools/remove_test_library.py` with Kodi closed; the orphan purge runs on next boot. (Never happens on a fresh device.) |

Kodi log lines are prefixed `[plugin.video.unknown.debrid]` and `[service.unknown.widgets]`.

## Development

```
tools/build_zips.py        builds dist/*.zip from the three addon folders
tools/build_repo.py        builds the installable repository (addons.xml + zips)
tools/make_test_library.py generates a placeholder TMDb library for UI work (PC only; key via --key-file or TMDB_API_KEY)
tools/remove_test_library.py / reset_video_library.py  PC-only dev cleanup
tools/repo_server.py       serves repo/ over HTTP on the LAN (only needed for --lan publishing)
publish-update.bat         one-click publish: build + push the repository to GitHub Pages
```

- **Publishing updates:** bump the version in the addon's `addon.xml`, double-click `publish-update.bat` — it rebuilds and pushes to GitHub Pages. Users' Kodi picks it up on their next repository refresh. No PC required afterwards.
- **Publishing to your LAN only:** `py tools/build_repo.py --lan` auto-detects this PC's IP and bakes it into the repository add-on (useful when testing without internet). The address is resolved at build time on the PC — the device fetching updates never needs to know or configure it. Override any target with the `UNKNOWN_REPO_URL` environment variable.
- **Why the repository add-on has no "change my IP" step:** by default it points at the GitHub Pages URL, which is public, static, and reachable from any device. A home LAN address would be private (never published) and dead for anyone outside the house — both bad. So the shipped add-on only ever carries the Pages URL.
- Build: `py -3 tools/build_zips.py` (Windows PowerShell 5.1, Python 3).
- Code style: Python 3.8 compatible (Kodi 20 on Android ships 3.8 — no `dict |`, `removeprefix`, or `list[int]` hints).
- The skin is a fork of Kodi's Estuary — keep the GPL-2.0 lineage intact (see LICENSE).
- The Real-Debrid plugin uses the public device-flow client ID (`X245A4XAIBGVM`); auth stores per-user credentials in Kodi's addon settings, never in the repo.

## FAQ

- **Does this download anything to my device?** No. The library is `.strm` pointers; playback streams from Real-Debrid. All your storage stays free.
- **How do I get movies into it?** Add a magnet/torrent on real-debrid.com (or any RD client), wait for `downloaded`, next sync appears in the library.
- **Does it remove what I remove from RD?** Yes — the next sync deletes the corresponding `.strm` files and cleans the library entries.
- **Can I watch while RD is still downloading?** No — only finished torrents stream. That's a Real-Debrid constraint, not the addon's.
- **Is my account shared anywhere?** No. Tokens stay in your Kodi's addon settings. Nothing in this repo speaks to anything except Real-Debrid's API (and TMDb for local scraping metadata).

## Disclaimer

This project is an unofficial integration with Real-Debrid. You are responsible for your Real-Debrid account, including what you store, what you stream, and how you use it in general. I am not responsible for how you choose to use the service. I do not host, control, or profit from any of the content used with this project or your Real-Debrid account. This project simply allows users to access their own content in an environment that most people are already familiar with, such as Netflix. Please use the project responsibly and at your own risk.

## License

GPL-2.0 — see [LICENSE](LICENSE).

`skin.unknown` is a fork of Kodi's Estuary skin (GPL-2.0). All other addons in this repository are original work distributed under the same license.
