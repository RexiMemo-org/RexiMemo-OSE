# RexiMemo OSE documentation

This is the repository copy of the manual served at `/docs` when RexiMemo OSE is started with `python3 server.py docs:enabled`. The web route is optional; this Markdown file is always available in the source tree.

This manual describes the Open Source Edition as it is shipped in this repository: the HTTP server, web client, Flipnote Studio resources, SQLite layout, media handling, identity model, moderation controls, assets and tests.

> **About the simplified OSE design.** A number of security, identity, moderation, networking and privacy mechanisms are intentionally much simpler here than on the private RexiMemo service. This is a release-safety boundary: the open-source tree avoids exposing production keys, authentication internals, trust checks, anti-abuse logic and deployment assumptions that could create security problems for the live service if published. The simpler replacements are easier to inspect and run independently, but they should not be mistaken for stronger security. Sections with an important consequence call this out explicitly.

## Contents

- [Starting the server](#start)
- [Repository layout](#shape)
- [Request routing](#request-routing)
- [Web client](#web)
- [Flipnote view page](#flipnote-page)
- [Flipnote Studio / DSi side](#dsi)
- [Posting a Flipnote](#posting)
- [Comments](#comments)
- [Accounts and IP login](#accounts)
- [Creator's Rooms](#rooms)
- [SQLite database](#database)
- [On-disk media](#files)
- [PPM, TMB, UGO, NTFT and NPF](#formats)
- [Image conversion code](#images)
- [Internal code reference](#code-reference)
- [Admin and bans](#admin)
- [Configuration](#configuration)
- [Assets and styling](#assets)
- [Tests](#tests)
- [Changing the server](#changing)
- [Deliberately absent systems](#limits)

## Starting the server

The entry point is `server.py`. A normal start is:

    python3 -m pip install -r requirements.txt
    python3 server.py

The default TCP port is `8080`. Set `REXIMEMO_PORT` before starting the process if another port is required. The process changes its working directory to the repository root before importing the server modules, so paths such as `database/`, `hatenadir/` and `web/static/` are resolved relative to the checkout rather than the shell's current directory.

The optional documentation site is enabled with an argument rather than being exposed by default:

    python3 server.py docs:enabled

When that argument is present, the server sets its documentation flag before constructing the Twisted resource tree. The web navigation gains a Docs item and `/docs` is served. Without the flag, there is no Docs navigation item and the same path follows the ordinary web 404 path.

`server.py` creates a Twisted `Site` subclass named `ProxyCompatibleSite`. Its only protocol alteration is for old-style absolute HTTP proxy requests. Before Twisted parses incoming bytes, request lines beginning with `GET http://flipnote.hatena.com`, `POST http://flipnote.hatena.com`, `GET http://ugomemo.hatena.ne.jp` or `POST http://ugomemo.hatena.ne.jp` are rewritten into origin-form request lines. This lets the same HTTP listener accept the historical proxy traffic used by Flipnote Studio and ordinary browser requests.

> **Network/security notice.** OSE deliberately does not reproduce RexiMemo's production NAS, DNS, certificate or authentication gateway. Those pieces are kept out of the public repository to reduce the risk of exposing live-service security logic, secrets or deployment assumptions. As a result, OSE is only the Hatena HTTP server/proxy portion: a DSi must obtain working Nintendo/Flipnote authentication through the official RexiMemo DNS service or another functional DNS/auth/NAS setup, then send Hatena HTTP traffic to this server as its proxy.

Logs are written to `logs/reximemo.log` and mirrored to standard output unless a call is marked silent. The `logs/` directory is runtime data and is not part of the repository.

## Repository layout

| Path                                       | Purpose                                                                                                                                                                                                       |
|--------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `.gitignore`                               | Excludes Python caches/virtual environments, logs, SQLite WAL/SHM sidecars, common key/certificate/token files, `.env` and Finder metadata from commits.                                                      |
| `server.py`                                | Process entry point, port selection, optional feature flags, logging and the proxy-compatible Twisted Site.                                                                                                   |
| `hatena.py`                                | Top-level HTTP resource router. It separates web traffic from DSi traffic, serves static CSS/images, loads the `hatenadir` resource tree and applies IP bans before either surface is reached.                |
| `reximemo.py`                              | Shared DSi helpers: regional URLs, current IP/account lookup, DSi keyboard values, DSi dialog/forward headers, UGO menu construction, pagination, PPM first-frame rendering and mini-Flipnote NPF conversion. |
| `webapp.py`                                | The normal browser client. It renders Home, Browse, About, optional Docs, Flipnote, Creator's Room, account and admin pages and exposes thumbnails, inline PPM playback media and counted PPM downloads.              |
| `docs_page.py`                             | The text of this built-in manual. It is imported by the web client only when the documentation route is requested.                                                                                            |
| `DB.py`                                    | Compatibility shim used by the older-style resource modules. It imports the single SQLite `Database` object and advertises `DB_type = "sqlite"`.                                                              |
| `database/__init__.py`                     | SQLite schema, seed data and all database operations used by the OSE server.                                                                                                                                  |
| `database/reximemo.sqlite3`                | Seed database supplied with the repository. It includes the default admin account, General channel, sample Creator's Rooms and three sample Flipnote records.                                                 |
| `database/Creators/`                       | PPM storage, grouped by creator FSID. The release contains three anonymised sample PPM files.                                                                                                                 |
| `database/Comments/`                       | Created/used for one-frame mini-Flipnote comment PPMs. Text comments stay entirely in SQLite.                                                                                                                 |
| `hatenadir/ds/v2-xx/`                      | Flipnote Studio HTTP resources. Python files are loaded into Twisted resources at start-up; the loader also supplies `.uls` aliases for `.ugo` resources.                                                     |
| `hatenadir/css/ds/common.css`              | Large compatibility stylesheet containing the old DSi HTML class names expected by the retained resource layout.                                                                                              |
| `hatenadir/css/ds/basic.css`               | Additional legacy/basic DSi styles. It overlaps a number of old service selectors but remains harmless for the small OSE page set.                                                                            |
| `hatenadir/css/ds/ose.css`                 | Short OSE override sheet that gives the DSi HTML pages their purple/green placeholder presentation and readable detail/comment styling.                                                                       |
| `hatenadir/images/ds/browse.ntft`          | 32×32 generated Browse menu icon.                                                                                                                                                                             |
| `hatenadir/images/ds/account.ntft`         | 32×32 generated Account menu icon.                                                                                                                                                                            |
| `hatenadir/images/ds/room.ntft`            | 32×32 generated Creator's Room menu icon.                                                                                                                                                                     |
| `hatenadir/images/ds/placeholder.npf`      | 128×64 generated indexed placeholder banner retained for DSi asset testing/use.                                                                                                                               |
| `web/static/site.css`                      | Complete browser stylesheet: colour variables, header/navigation, Flipnote grids, watch/player layout, playback controls, comments, forms, admin tables, documentation layout and responsive breakpoints.           |
| `web/static/flipnote-player.js`               | Small browser-side controller around flipnote.js. It loads the PPM, updates play/pause, seek, sound, loop and time controls, and restores the first-frame fallback if playback is unavailable.                         |
| `web/static/RexiMemo_OSE_Logo.png`         | White RexiMemo logo with “Open Source Edition” included in the image itself.                                                                                                                                  |
| `Hatenatools/__init__.py`                  | Convenience exports for `PPM`, `TMB`, `UGO` and `NTFT`.                                                                                                                                                       |
| `Hatenatools/PPM.py`                       | Legacy Flipnote Studio PPM/TMB parser: metadata, thumbnail data, frame decoding, sound decoding and helper dump functions. OSE mainly uses `PPM.Read()`, `PPM.GetFrame()` and `TMB.Read()`.                   |
| `Hatenatools/UGO.py`                       | Legacy UGO/UGAR parser/packer. OSE builds DSi menus by appending layout, top-screen text, category, post and button items then calling `Pack()`.                                                              |
| `Hatenatools/NTFT.py`                      | Legacy NTFT reader/writer retained for compatibility and format work. OSE's generated placeholders use the newer encoder in `reximemo_image_formats.py`.                                                      |
| `Hatenatools/ReadMe.txt`                   | Original Hatenatools version notes, format summary and contributor credits.                                                                                                                                   |
| `Hatenatools/License.txt`                  | The Hatenatools AGPL licence text shipped with that code.                                                                                                                                                     |
| `Hatenatools/hatenatools project page.url` | Legacy Internet Shortcut retained with the upstream helper sources.                                                                                                                                           |
| `reximemo_image_formats.py`                | Independent image codec helpers for NTFT, NPF and NBF plus standard Pillow-backed image formats.                                                                                                              |
| `tools/generate_placeholders.py`           | Rebuilds the plain DSi placeholder icons and banner from simple geometric shapes.                                                                                                                             |
| `tests/test_database.py`                   | Temporary-database checks for seed admin, IP login/logout, guest room stability and bans.                                                                                                                     |
| `tests/test_resources.py`                  | Twisted-stub resource tests covering the DSi tree, UGAR menu generation, web routes, watch-page detail, Docs gating and PNG thumbnail generation.                                                             |
| `tests/test_release_shape.py`              | Release checks preventing key/certificate/font file types, named removed production components and sample-content drift.                                                                                      |
| `requirements.txt`                         | Runtime Python dependencies: Twisted, NumPy and Pillow.                                                                                                                                                       |
| `README.md`                                | Short installation/release overview.                                                                                                                                                                          |
| `DOCS.md`                                  | GitHub-readable copy of this detailed technical reference. The built-in `/docs` page and this file are intended to carry the same operational information.                                                    |
| `LICENSE`                                  | GNU Affero General Public License version 3.                                                                                                                                                                  |

The three sample PPM paths are `database/Creators/A000000000000001/000001_OSEOPEN000001_000.ppm`, `...0002/000002_OSEOPEN000002_001.ppm` and `...0003/000003_OSEOPEN000003_002.ppm`. Their matching public Flipnote IDs are `f_sample1` through `f_sample3`; their Creator's Room public IDs are `r_sample1` through `r_sample3`.

## Request routing

`hatena.Setup()` returns a `Root` resource. Every request first reaches that object. The source IP is checked against `ip_bans` before web or DSi routing. A blocked address receives a plain `403` response.

The request's `Host` header determines which surface is selected. `flipnote.hatena.com` and `ugomemo.hatena.ne.jp` are treated as DSi hosts. Everything else, including `localhost` and a normal server hostname, is sent to `WebRoot`.

DSi-host requests must contain `X-DSi-SID`. OSE does not validate or decode the SID; the header is only the transport-side gate expected by this reduced resource tree. A missing header produces the access-denied resource. This is deliberately separate from account state: an IP may have a web/DSi OSE account login row while DSi-host routing still requires the header.

> **Identity notice.** `X-DSi-SID` is a compatibility marker in OSE, not proof of a particular console or account. Production SID/device verification, FSID ownership checks and related anti-abuse systems were intentionally removed rather than publishing their implementation. This keeps the public DSi path small, but callers must not treat the header as a security credential.

Static top-level routes are handled before host routing. `/css/` maps to `hatenadir/css/`, `/images/` maps to `hatenadir/images/`, and `/static/` maps to `web/static/`. This mirrors the old server shape while keeping browser assets separate from DSi assets.

The DSi region root recognises `v2-xx`, `v2-eu`, `v2-us` and `v2-jp`. All four currently use the same loaded `v2-xx` implementation. URL generation switches the Japanese host to `ugomemo.hatena.ne.jp`; the other regions use `flipnote.hatena.com`.

## Web client

The browser client is server-rendered HTML in `webapp.py`. It has no JavaScript framework and no browser session cookie. Each request asks the database for the account currently associated with the source IP.

> **Login notice.** The web client uses the same deliberately simple IP identity model as the rest of OSE. Production session/device management was left out so that live authentication design, keys and account-security machinery are not copied into a public release. Shared addresses, proxies and changing IPs therefore have consequences described in the Accounts section below.

| Route                        | Method   | Behaviour                                                                                                                           |
|------------------------------|----------|-------------------------------------------------------------------------------------------------------------------------------------|
| `/`                          | GET      | Home page with the most recent Flipnotes.                                                                                           |
| `/browse`                    | GET      | Browse up to 100 Flipnotes. `?sort=new`, `?sort=popular` and `?sort=top` map to posted time, views/stars and stars/views orderings. |
| `/about`                     | GET      | Open-source credits and acknowledgements only.                                                                                      |
| `/docs`                      | GET      | This manual, only when documentation is enabled at server start.                                                                    |
| `/watch/<public id>`         | GET      | Flipnote detail page. It increments the view count, loads comments and shows other notes from the same Creator's Room.              |
| `/watch/<public id>/comment` | POST     | Adds a text comment using the current account or guest-IP Creator's Room.                                                           |
| `/thumb/<public id>.png`     | GET      | Decodes the first PPM frame and returns a cached PNG thumbnail.                                                                     |
| `/comment-thumb/<id>.png`    | GET      | Returns a first-frame PNG preview for a mini-Flipnote comment.                                                                      |
| `/media/<public id>.ppm`     | GET      | Returns the original PPM inline for browser playback. It does not increment the download counter.                                                |
| `/flipnote/<public id>.ppm`  | GET      | Increments downloads and returns the original PPM as an attachment.                                                                 |
| `/creator/<public id>`       | GET      | Creator's Room with its Flipnote grid and account/guest ownership label.                                                            |
| `/login`                     | GET/POST | Username/password sign-in. Successful POST writes an `ip_logins` row for the source IP.                                             |
| `/register`                  | GET/POST | Creates an account and immediately associates the source IP with it.                                                                |
| `/logout`                    | GET      | Deletes the current source IP from `ip_logins`.                                                                                     |
| `/account`                   | GET      | Shows the signed-in username, current IP and Creator's Room link when one exists.                                                   |
| `/admin`                     | GET      | Minimal administrator view for IP bans and Flipnote deletion.                                                                       |
| `/admin/ban`                 | POST     | Adds or updates an IP ban and clears that IP's login row.                                                                           |
| `/admin/unban`               | POST     | Removes an IP ban.                                                                                                                  |
| `/admin/delete`              | POST     | Soft-deletes a Flipnote record by setting `deleted=1`.                                                                              |

The common page wrapper builds the header, navigation, account/admin actions and footer. Docs is inserted into that navigation only when the `WebRoot` instance was created with documentation enabled.

## Flipnote view page

The watch page has browser playback as well as the server-generated first-frame fallback. `webapp.py` loads the pinned `flipnote.js` 6.3.1 browser build from jsDelivr, then loads the local `web/static/flipnote-player.js` controller. The controller creates a `flipnote.Player` at 320×240, asks it to load `/media/<public id>.ppm`, and lets flipnote.js decode the original PPM animation and audio in the browser. OSE does not pre-render a video, GIF or separate audio file.

The player starts paused. Once flipnote.js reports that the note is ready, OSE hides the first-frame image and enables the large play button and the control row. The controls provide play/pause, a seek range, elapsed/total time, sound mute/unmute and loop on/off. Seeking uses flipnote.js's `startSeek()`, `seek()` and `endSeek()` calls so playback can resume cleanly after dragging. Clicking the rendered Flipnote toggles playback after the player has been started once.

`/media/<public id>.ppm` is deliberately separate from `/flipnote/<public id>.ppm`. The media route returns the same on-disk PPM with `Content-Disposition: inline` and a one-hour public cache header, but it does not call `Database.AddDownload()`. The download route remains the explicit **Download PPM** action, increments the download counter and returns the file as an attachment. Opening or replaying a watch page therefore does not count as a file download.

The `<img>` first-frame preview remains in the page before JavaScript runs. If the flipnote.js global is missing, the browser cannot construct its canvas/WebAudio player, the PPM cannot be parsed, or playback reports an error, `flipnote-player.js` leaves that preview visible, disables the player controls and shows a short playback-unavailable message. The rest of the watch page still works normally. This also gives the page a useful non-JavaScript fallback.

> **Browser dependency/privacy notice.** The playback library is loaded from the jsDelivr CDN rather than copied into OSE. This keeps a large third-party build out of the repository, but it means a browser visiting a watch page makes a request to jsDelivr for `flipnote.min.js`. The PPM URL itself is same-origin and is not submitted to jsDelivr by OSE. An operator who does not want that third-party browser request should self-host the pinned flipnote.js build and change the script URL in `webapp.py`.

Opening the page calls `Database.AddView()` before the Flipnote row is reloaded, so the displayed view count includes the current request. The page then loads up to 100 comments, the channel record, the Creator's Room record and a short list of other non-deleted Flipnotes from the same room.

The information panel displays stars, views, downloads and comment count, then the post time, channel, creator FSID, PPM filename and public identifier. These values come directly from the OSE SQLite row; there is no secondary profile, device or ownership lookup.

> **Metadata notice.** Creator metadata shown here is repository data, not a cryptographically verified identity. OSE deliberately avoids the production ownership/device verification chain so those security mechanisms are not exposed in the public codebase. Treat FSIDs, embedded creator names and room ownership as local OSE identifiers.

Text comments are HTML-escaped. Mini-Flipnote comments are shown as first-frame thumbnails through `/comment-thumb/<id>.png`; the stored PPM is still the authoritative comment file used by the DSi endpoints.

## Flipnote Studio / DSi side

### Connecting a DSi

RexiMemo OSE does not contain the authentication/NAS or DNS service needed to get a DSi through the normal Nintendo/Flipnote connection path. Use the official RexiMemo DNS service, or another working DNS setup that also provides the required authentication/NAS behaviour for Flipnote Studio.

1.  Configure the DSi internet connection to use the official RexiMemo DNS service, or another known-working DNS/auth/NAS service.
2.  In the same DSi connection settings, enable the HTTP **Proxy Server**.
3.  Set the proxy server address to the IP address of the machine running RexiMemo OSE.
4.  Set the proxy port to `8080`, unless `REXIMEMO_PORT` was deliberately changed on the OSE server.
5.  Start OSE with `python3 server.py` and then open Flipnote Studio/Flipnote Hatena on the DSi.

DNS/auth/NAS and the Hatena HTTP proxy are separate jobs in this arrangement. The external DNS/auth/NAS service gets the console through the authentication path; RexiMemo OSE handles the Hatena web requests that the DSi sends to the configured proxy.

> **Connection/security notice.** The missing auth/NAS stack is deliberate. OSE uses an external working service instead of publishing RexiMemo's private authentication and network-security implementation. Do not copy private keys, production credentials or live authentication code into an OSE checkout to make up for the missing component. Point the DSi at an authorised working DNS/auth/NAS service and keep OSE limited to the proxy/server role it was released for.

The DSi surface is built from Twisted resources under `hatenadir/ds/v2-xx`. `hatena.LoadHatenadirStructure()` walks that directory at start-up. Ordinary files become static resources. A filename ending in `.py` is imported as a module and its `PyResource()` object is mounted under the filename without `.py`. Any resulting resource whose mounted name ends in `.ugo` is also mounted under the equivalent `.uls` name.

| Resource              | Function                                                                                                                                                                                                   |
|-----------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `index.ugo.py`        | Home UGO menu. It shows Browse, Account, the current Creator's Room when one exists, then recent Flipnotes. Menu icons are the generated 32×32 NTFT placeholders.                                          |
| `allflipnotes.ugo.py` | Paginated all-Flipnotes UGO list. It uses 50 Flipnotes per page and adds Previous/Next buttons when required.                                                                                              |
| `ch.py`               | Channel browse and posting. `ch/1.uls` lists channel Flipnotes; `ch/1.htm` is a small HTML description; POST to `ch/1.post` accepts a PPM and stores it.                                                   |
| `creator.py`          | Creator's Room resources. It accepts the numeric internal room ID and serves `profile.htm`, `room.uls` and `movies.uls`. `room.ugo`/`movies.ugo` are accepted as aliases.                                  |
| `movie.py`            | Flipnote PPM/TMB/details, star, download and comment endpoints.                                                                                                                                            |
| `comment.py`          | Stored mini-Flipnote comment delivery as raw `.ppm` or generated `.npf` preview.                                                                                                                           |
| `sa.py`               | Simple DSi account pages and keyboard-based login/register/logout flow.                                                                                                                                    |
| `inbox.ugo.py`        | Empty compatibility page stating that notifications are not included.                                                                                                                                      |
| `eula_list.tsv`       | Static compatibility row containing the base64-encoded “English” label and `en` language code. It is retained because older clients/resources may request the file even though OSE has no terms/EULA flow. |

UGO menu data is assembled by `reximemo.make_menu()` through Hatenatools' `UGO` class. Thumbnail buttons embed the first `0x6A0` bytes of a PPM as TMB data. Icon buttons embed a 32×32 NTFT and are rejected if the byte length is not exactly 2048.

The DSi HTML helper links `common.css`, `basic.css` and `ose.css` from the Hatena host. These pages deliberately stay small and old-browser friendly: basic HTML, tables, metadata tags and CSS with no JavaScript dependency.

## Posting a Flipnote

1.  Flipnote Studio POSTs PPM bytes to a channel `.post` resource.
2.  `ch.py` reads the request body and asks `current_account()` whether the source IP is signed in.
3.  `Database.AddFlipnote()` parses the PPM header through Hatenatools `TMB().Read()`.
4.  The editor author ID becomes the stored creator FSID. `CurrentFilename` supplies the base filename. If either value is missing, or the same FSID/filename already exists, the post is refused.
5.  The embedded username/editor name is used as the display-name hint.
6.  `get_or_create_creator()` obtains the account-owned room or guest-IP room. This is the point at which a Creator's Room is automatically created for a first post.
7.  The requested channel is checked; an unknown channel falls back to channel 1.
8.  A Flipnote row is created with a new public ID beginning `f_`.
9.  The exact submitted PPM bytes are written to `database/Creators/<FSID>/<filename>.ppm`.

No web PPM upload route exists. Browser users can browse/download/comment, but new Flipnotes enter OSE through the Flipnote Studio channel post path.

> **Posting notice.** OSE reads the creator FSID, username and filename from the submitted PPM, but it does not perform the production FSID ownership or PPM signature-verification steps. Those systems were removed to avoid releasing production trust logic and key-dependent verification code. The simpler OSE path is intended for a small self-hosted/test environment; do not interpret embedded PPM identity fields as independently proven.

## Comments

### Text comments

Web text comments POST a normal form field named `text`. DSi text comments use the keyboard endpoint and read the value from `X-Email-Addr`, matching the old keyboard transport convention. The database collapses whitespace, truncates to 500 characters and rejects an empty result.

A comment needs a Creator's Room. If the source IP is logged in, the room belongs to that account. Otherwise a room is created or reused for the source IP. The stored comment references only the room ID; display names shown later are joined from `creator_rooms`.

### Mini-Flipnote comments

A POST to a Flipnote's `.reply` endpoint is parsed as PPM/TMB. OSE requires exactly one frame. The PPM's author ID and embedded username are passed into the same room-creation function, then the comment row is inserted as type `memo`. Its binary PPM is written to `database/Comments/<comment id>.ppm` and that filename is stored in the row.

For the DSi comment preview, `comment_npf()` decodes the first PPM frame, resizes it to the requested dimensions and encodes it as NPF. Width is clamped to 1–256 and height to 1–192. The raw mini-Flipnote remains available through its `.ppm` comment route.

> **Comment identity notice.** Guest comments are attached to an IP-backed Creator's Room, and mini-Flipnote identity hints come from the submitted PPM. This is intentionally simpler than production moderation/account attribution so the public tree does not contain the production device, session and ownership-verification stack. On shared networks, more than one person can therefore appear under the same guest identity.

## Accounts and IP login

Accounts are optional. Usernames are 3–24 characters and may contain ASCII letters, numbers, dots, dashes and underscores. Passwords must contain at least four characters. The OSE database stores a SHA-256 digest in `password_sha256`.

> **Account security notice.** Accounts are deliberately implemented in a much simpler form than the private service. Production password/session/device security, passkeys, recovery flows, per-device state and authentication-gateway logic are not published here because doing so could expose security-sensitive implementation details or assumptions from the live service. OSE substitutes a small local model so the public code can stand alone. That release choice limits what sensitive production material is exposed; it does not make the replacement stronger. Unsalted SHA-256 is not a modern password-storage scheme and the minimum password rule is intentionally small.

OSE login state is tied to your IP address. `login_ip()` upserts one `ip_logins` row whose primary key is the source IP. If that address logs into a different account, the row is replaced with the new account ID. `account_for_ip()` joins the row to `accounts` and refreshes `last_seen`. Logout deletes the row.

There are no cookies or browser session identifiers in this flow. The DSi and browser clients see the same account when they reach the server from the same source IP. If traffic is behind a shared NAT or reverse proxy, the address visible to Twisted is the identity key used by OSE.

> **IP login notice.** An IP address is only a convenient OSE ownership key. Addresses can be shared, reassigned, hidden behind NAT or represented by a reverse proxy. OSE uses this simpler local mapping so the public release does not contain RexiMemo's production session/device security implementation, reducing the risk of exposing live-service authentication behaviour. It is a release-safety compromise, not a secure substitute for a proper session design.

The DSi account page uses `username:password` entered through the Flipnote Studio keyboard. The keyboard value arrives in `X-Email-Addr`. Registration creates the account, writes the IP login, and forwards back to `sa/account.htm` using `X-DSi-Forwarder`.

The seeded administrator is `reximemo` with password `alpine`. It is created only when no account named `reximemo` exists in the opened database.

> **Default credential notice.** The seed login exists so a fresh checkout can exercise the admin page immediately. It is public repository data, not a secret. Change or remove it before exposing an OSE instance beyond a controlled test network.

## Creator's Rooms

A room has an internal integer ID and a public ID beginning `r_`. Account rooms have `account_id` set and normally have no `owner_ip`. Guest rooms have `owner_ip` set and no account ID. SQLite uniqueness rules permit only one room per account and one guest room per stored IP.

For an account, the displayed room name is the account username. A first observed FSID can fill an empty room FSID. For a guest, the first room name is either the PPM-provided creator name or a deterministic `Guest-XXXXXX` value derived from the IP with SHA-1. If a guest room still has the generated Guest name, a later PPM with a display name can replace it.

The web uses the room's public ID in URLs. The DSi resource tree primarily uses the internal numeric room ID for Creator's Room paths. `UgoRoot` also recognises a 16-hex-character path component and can resolve a room from its FSID before passing into the creator resource.

> **Room ownership notice.** Account ownership and guest-IP ownership are convenience rules inside this OSE database. They do not reproduce production creator verification. This design deliberately avoids carrying production account/device linkage and FSID proof into the public repository, so room ownership should be understood as local OSE state rather than an authoritative Nintendo/Flipnote identity claim.

## SQLite database

`DatabaseBackend` opens `database/reximemo.sqlite3` unless `REXIMEMO_DB` points elsewhere. `check_same_thread=False` is used because Twisted/resource code may access the shared connection outside SQLite's default creating-thread check. A re-entrant Python lock wraps writes and related grouped operations. Foreign keys are enabled and journal mode is set to WAL.

| Table           | Important fields                                                                    | Meaning                                                      |
|-----------------|-------------------------------------------------------------------------------------|--------------------------------------------------------------|
| `accounts`      | `username`, `password_sha256`, `is_admin`, `created_at`                             | Optional local web/DSi account.                              |
| `ip_logins`     | `ip` primary key, `account_id`, `last_seen`                                         | Current IP-to-account association.                           |
| `ip_bans`       | `ip` primary key, `reason`, `created_at`                                            | Addresses denied before routing.                             |
| `creator_rooms` | `public_id`, `account_id`, `owner_ip`, `fsid`, `display_name`                       | Identity/ownership container used by Flipnotes and comments. |
| `channels`      | `id`, `title`, `description`                                                        | Posting/browse channel. OSE seeds channel 1 as General.      |
| `flipnotes`     | `public_id`, room, FSID, filename, title, channel, counters, `posted_at`, `deleted` | Metadata for each stored PPM.                                |
| `comments`      | `public_id`, Flipnote, room, `type`, text/memo filename, `posted_at`, `deleted`     | Text or one-frame mini-Flipnote comments.                    |

`flipnotes` has a uniqueness constraint on `(creator_fsid, filename)`. Public IDs are generated from `secrets.token_urlsafe()`, stripped of `-`/`_`, truncated, and prefixed according to object type. They are routing identifiers rather than authentication tokens.

> **Database/privacy notice.** OSE stores usernames, password digests, source IP login mappings, guest owner IPs and IP bans directly in SQLite. This is deliberately straightforward so the public release has no hidden account/session service or production datastore dependency. If you run a public instance, decide what IP retention, access control, backups and database-file permissions are appropriate for your environment.

Flipnote deletion is a soft delete. Listing and lookup queries require `deleted=0`; the PPM file is not erased by `delete_flipnote()`. Comments also carry a `deleted` column, although the OSE web admin does not expose comment moderation controls.

Sorting rules are defined in `list_flipnotes()`. Newest uses `posted_at DESC, id DESC`; Popular uses views, then stars, then posted time; Stars uses stars, then views, then posted time.

## On-disk media

SQLite holds metadata; PPM bytes are kept as files. A Flipnote path is constructed as:

    database/Creators/<upper-case FSID>/<filename>.ppm

The PPM filename stored in SQLite does not include `.ppm`. `GetFlipnotePPM()` reads the whole file. `GetFlipnoteTMB()` reads only the first `0x6A0` bytes for menu thumbnails. Browser playback does not create another media file: `/media/<public id>.ppm` reads and returns this same PPM, while `/flipnote/<public id>.ppm` reads the same file through the counted download path.

Mini comments use:

    database/Comments/<numeric comment id>.ppm

The database stores that basename in `memo_filename`. The numeric filename is assigned after the row insert because the SQLite row ID is used as the stable file name.

The release's three example PPMs use sample FSIDs and rewritten sample metadata. They are present so the web/DSi browse paths, thumbnail decoder and download routes can be tested immediately after cloning.

> **Storage notice.** Flipnotes and mini-Flipnote comments are ordinary files on disk and are not encrypted by OSE. A soft-deleted Flipnote row also leaves its PPM file in place. The storage model is intentionally transparent and dependency-free; operators who need stronger deletion, encryption, retention or backup guarantees should add them outside or on top of this repository.

## PPM, TMB, UGO, NTFT and NPF

### PPM and TMB

PPM is the Flipnote Studio animation container handled by `Hatenatools/PPM.py`. OSE uses the full PPM parser when it needs a decoded frame or mini-Flipnote validation. It uses `TMB().Read()` for metadata-oriented work such as FSID, username, filename and frame count. For menu thumbnails the first `0x6A0` bytes are served directly as TMB data.

> **Parser notice.** Hatenatools is retained primarily for compatibility with these old file formats. OSE deliberately does not wrap it in the full set of production upload validation, signature checks, anti-abuse controls and isolation measures. Treat arbitrary files from an untrusted public upload source as untrusted input and add the controls suitable for that deployment.

`ppm_first_frame_image()` asks Hatenatools to read frames but not sound, obtains frame zero, converts the returned array in Fortran order and constructs a Pillow RGBA image. Browser thumbnails convert that image to RGB and resize with nearest-neighbour resampling.

### UGO / UGAR

Flipnote Studio menu screens are packed with Hatenatools `UGO`. `make_menu()` begins with a layout item, optionally adds top-screen title data and category/dropdown items, then encodes each button. Flipnote buttons embed TMB thumbnails; OSE navigation buttons embed generated NTFT icons. The packed result begins with the UGAR container signature used by the test suite.

### NTFT

NTFT assets are raw 16-bit ABGR1555 pixels. Dimensions are external to the file. A 32×32 NTFT therefore occupies exactly 2048 bytes. The OSE UGO helper enforces that size for embedded menu icons.

### NPF

NPF is a 4-bit indexed image format with a transparent index and up to 15 opaque colours. OSE uses it for mini-Flipnote comment previews and one generated placeholder banner. Width and height are supplied by the caller because the raw image dimensions are not stored in the NPF payload.

### NBF

`reximemo_image_formats.py` also retains NBF encode/decode support. NBF is an 8-bit indexed format with up to 256 opaque colours. There is no current OSE HTTP endpoint that requires NBF; the codec remains useful for working with related DSi assets.

## Image conversion code

`reximemo_image_formats.py` is a self-contained converter for Nintendo-oriented and standard still-image formats. The proprietary set is `ntft`, `npf` and `nbf`. Standard outputs are PNG, JPEG, WebP, BMP and GIF.

Input dimensions are validated before large allocations: each side is limited to 2048 pixels and total area to 4,194,304 pixels. Raw formats whose dimensions are not embedded require width/height from the caller. ABGR1555 packing/unpacking is implemented directly. Indexed formats use Pillow quantisation after conversion to a reduced 5-bit colour space, which better matches the source pixel formats.

The public encoder returns an `EncodedImage` dataclass containing bytes, format key/label, extension, MIME type, preview image and format note. The decoder returns a `DecodedImage` with the corresponding image and metadata. JPEG/BMP paths flatten transparency onto white; GIF output is one still frame.

`tools/generate_placeholders.py` uses this encoder. It draws three 32×32 icons and one 128×64 banner with Pillow primitives and writes NTFT/NPF bytes into `hatenadir/images/ds`.

## Internal code reference

This section lists the small internal API that joins the repository together. Names are included because most extensions to OSE can be made by following these existing call paths rather than adding another framework layer.

### `hatena.py`

| Name                                  | Role                                                                                                                                                            |
|---------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `as_text(value)`                      | Converts bytes to UTF-8 text with replacement for malformed sequences; all other values are stringified.                                                        |
| `request_path(request)`               | Returns the request path as text.                                                                                                                               |
| `request_headers(request)`            | Builds a lower-case text-keyed dictionary from Twisted's request headers.                                                                                       |
| `request_args(request)`               | Converts Twisted's byte query arguments into a text dictionary whose values remain lists.                                                                       |
| `client_ip(request)`                  | Reads `getClientIP()` first and falls back to `getClientAddress().host`. The returned string is the key used by OSE login, guest ownership and bans.            |
| `Log(request, path=None, silent=...)` | Writes a short source-IP/request-path entry through the process logger when one is attached.                                                                    |
| `AccessDeniedResource`                | Plain 403 used when DSi-host traffic does not carry `X-DSi-SID`.                                                                                                |
| `BannedResource`                      | Plain 403 used for an IP present in `ip_bans`.                                                                                                                  |
| `NotFoundResource`                    | Plain 404 resource which also records the path/query in the log.                                                                                                |
| `Root`                                | Top-level static/host router. It owns the web root, DSi root and static directory resources.                                                                    |
| `DSRoot`                              | Recognises supported `v2-*` region names and forwards each to the shared UgoRoot.                                                                               |
| `UgoRoot`                             | Loads `hatenadir/ds/v2-xx`. It also resolves a bare 16-hex FSID path to a Creator's Room when possible.                                                         |
| `FileResource`                        | Static DSi file wrapper. Files whose extension starts with `htm` receive an HTML content type.                                                                  |
| `FolderResource`                      | Container for recursively loaded directories. Direct rendering is forbidden with 403.                                                                           |
| `LoadHatenadirStructure()`            | One-level-at-a-time recursive loader. Python resources are imported by absolute path with a SHA-1-derived module name to avoid ordinary module-name collisions. |
| `Setup(docs_enabled=False)`           | Constructs the root resource and passes the documentation switch into the browser `WebRoot`.                                                                    |

### `reximemo.py`

| Name                      | Role                                                                                                                   |
|---------------------------|------------------------------------------------------------------------------------------------------------------------|
| `region_from_request()`   | Finds the first path segment beginning `v2-` and returns its region suffix; defaults to `xx`.                          |
| `host_for_region()`       | Returns the Japanese Ugomemo host for `jp`, otherwise the main Flipnote host.                                          |
| `dsi_url()`               | Builds an absolute historical-style DSi URL using the current request region.                                          |
| `current_account()`       | Looks up the source IP in `ip_logins`.                                                                                 |
| `current_creator()`       | Convenience call into `get_or_create_creator()` using the request IP/current account and optional PPM identity hints.  |
| `keyboard_value()`        | Returns the stripped `X-Email-Addr` header used by Flipnote Studio keyboard submissions.                               |
| `dialog()`                | Sets an HTTP status, `X-DSi-Dialog-Type: 1`, plain content type and UTF-16LE message body.                             |
| `forward()`               | Sets `X-DSi-Forwarder` to tell the DSi browser which resource to open next.                                            |
| `html_page()`             | Produces the minimal DSi HTML wrapper, top-screen title metadata and three DSi stylesheets.                            |
| `query_int()`             | Reads a query argument as an integer and clamps it to caller-supplied minimum/maximum bounds.                          |
| `make_menu()`             | Builds an in-memory UGO menu from layout/title/category/post/button dictionaries, including embedded TMB or NTFT data. |
| `placeholder_icon()`      | Reads one generated NTFT file from `hatenadir/images/ds`.                                                              |
| `flipnote_buttons()`      | Turns database Flipnote rows into UGO thumbnail buttons; unreadable PPM/TMB files are skipped.                         |
| `pagination_buttons()`    | Calculates page count and returns Previous/Next UGO button dictionaries.                                               |
| `ppm_first_frame_image()` | Decodes PPM frame zero into a Pillow RGBA image.                                                                       |
| `ppm_thumbnail_png()`     | Creates a nearest-neighbour RGB PNG thumbnail from frame zero.                                                         |
| `comment_npf()`           | Loads a stored mini-comment PPM, decodes/resizes its first frame and returns NPF bytes.                                |

### `DatabaseBackend`

> **Implementation notice.** Several database methods below deal with login, ownership and moderation. Their small size is intentional: the OSE implementation replaces production session/device/security services with local SQLite operations so private operational logic is not exposed. Method names such as `verify_account()` describe what they do inside OSE, not a claim that they provide production-grade identity verification.

| Method/property                                                         | Role                                                                                                                                 |
|-------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------|
| `create_account()`                                                      | Validates username/password, hashes the password and inserts a non-admin account.                                                    |
| `verify_account()`                                                      | Hashes the supplied password and queries by username plus digest.                                                                    |
| `get_account()` / `get_account_by_username()`                           | Direct account lookup helpers.                                                                                                       |
| `login_ip()`                                                            | Upserts the one login row for an IP and records `last_seen`.                                                                         |
| `logout_ip()`                                                           | Deletes an IP login row.                                                                                                             |
| `account_for_ip()`                                                      | Joins login to account and refreshes `last_seen` when found.                                                                         |
| `is_ip_banned()`, `ban_ip()`, `unban_ip()`, `list_bans()`               | Exact-IP moderation operations. Banning also signs that IP out.                                                                      |
| `get_creator_room*`                                                     | Room lookups by numeric ID, public ID or FSID.                                                                                       |
| `room_for_account()` / `room_for_ip()`                                  | Ownership lookups used before automatic room creation.                                                                               |
| `get_or_create_creator()`                                               | Central account/guest identity resolver. It creates the room on first use and fills previously empty FSID/name fields when suitable. |
| `list_creator_flipnotes()`                                              | Thin room-filtered wrapper around `list_flipnotes()`.                                                                                |
| `get_channel()` / `list_channels()`                                     | Channel metadata access.                                                                                                             |
| `FlipnotePath()`                                                        | Returns the PPM filesystem path for an FSID/filename pair.                                                                           |
| `CreatorExists()`                                                       | True when a room with the FSID exists or the corresponding creator directory exists.                                                 |
| `FlipnoteExists()`                                                      | Requires both a non-deleted database row and an existing PPM file.                                                                   |
| `AddFlipnote()`                                                         | Parses TMB identity/filename, resolves the room/channel, inserts metadata and writes PPM bytes.                                      |
| `get_flipnote()`, `get_flipnote_by_id()`, `get_flipnote_by_public_id()` | Joined non-deleted Flipnote/Creator's Room lookups.                                                                                  |
| `GetFlipnote()`                                                         | Compatibility wrapper returning a row or `False`.                                                                                    |
| `GetFlipnotePPM()` / `GetFlipnoteTMB()`                                 | Reads whole PPM bytes or the first `0x6A0` thumbnail/metadata bytes.                                                                 |
| `list_flipnotes()`                                                      | Filtered, sorted, paginated Flipnote query used by both web and DSi lists.                                                           |
| `count_flipnotes()`                                                     | Counts non-deleted Flipnotes globally or by channel/room.                                                                            |
| `Newest`                                                                | Compatibility property returning `(creator_fsid, filename)` pairs for all current notes.                                             |
| `Views` / `Stars`                                                       | Aggregate counters over non-deleted Flipnotes.                                                                                       |
| `AddView()`, `AddDownload()`, `AddStar()`                               | Atomic counter increments. Star amounts are clamped to 1–65535.                                                                      |
| `delete_flipnote()`                                                     | Sets `deleted=1` for the row.                                                                                                        |
| `add_text_comment()`                                                    | Normalises/truncates text, resolves a Creator's Room and inserts a text comment.                                                     |
| `add_memo_comment()`                                                    | Parses PPM metadata, resolves a room, inserts the row, writes `<id>.ppm` and updates `memo_filename`.                                |
| `get_comment()` / `list_comments()` / `count_comments()`                | Non-deleted comment access with Creator's Room display information.                                                                  |
| `comment_ppm()`                                                         | Loads bytes for a memo-type comment when the row and file are present.                                                               |
| `recent_ip_logins()`                                                    | Returns recent IP/account associations ordered by `last_seen`. The current minimal admin page does not display this helper.          |

### `reximemo_image_formats.py` public surface

`decode_uploaded_image()` accepts bytes plus a filename/input-format hint and optional raw dimensions. It normalises standard image formats through Pillow and raw Nintendo formats through the local decoders, then returns `DecodedImage`. There is no current OSE web upload route using this function; it remains a reusable format utility.

`encode_image()` accepts a Pillow image and an output format key. It delegates to the proprietary encoders or Pillow standard writers and returns `EncodedImage`. `image_characteristics()` reports useful source properties such as size/mode/alpha. `ConversionError` is the module's input/format validation exception.

## Admin and bans

An account reaches `/admin` only when `is_admin` is 1. OSE's admin page has two jobs: maintain `ip_bans` and soft-delete Flipnotes.

Banning inserts or updates the exact text IP value and removes any login row for that address. The top-level router checks bans on every request, so a banned address cannot reach the browser pages, DSi resources or static content through the normal root resource.

Unban deletes the matching row. There are no subnet rules, expiry times, device bans, case queues, strike systems or hidden moderation states. The optional reason is limited to 200 characters and is only shown in the admin table.

> **Moderation notice.** IP banning and soft deletion are intentionally much simpler than RexiMemo's private moderation system. OSE leaves out device bans, behavioural/bot detection, case tooling and other production anti-abuse logic so those systems are not disclosed in a public release. Exact-IP bans are easy to understand but can affect shared networks and can be bypassed when a user's public address changes.

## Configuration

| Setting         | Default                     | Use                                                                                                                |
|-----------------|-----------------------------|--------------------------------------------------------------------------------------------------------------------|
| `REXIMEMO_PORT` | `8080`                      | TCP listen port read by `server.py`.                                                                               |
| `REXIMEMO_DB`   | `database/reximemo.sqlite3` | Alternative SQLite file path read when `DatabaseBackend` is constructed.                                           |
| `docs:enabled`  | off                         | Command-line flag enabling the built-in web documentation route and navigation item.                               |
| DSi proxy       | server IP, port `8080`      | Set in the DSi connection settings. OSE is the Hatena HTTP proxy/server; DNS/auth/NAS must be supplied separately. |

There is no separate configuration file parser in OSE. Channel 1 and the default administrator are database seed data. DSi host names are constants in `reximemo.py`/`hatena.py`.

> **Configuration notice.** OSE favours explicit, visible defaults over a production secrets/configuration stack. Do not place private keys, service tokens or live production credentials into the repository to compensate for missing configuration features. Keep deployment secrets outside the checkout and change the public seed administrator if the instance is reachable by others.

## Assets and styling

The web interface uses `web/static/site.css` and `web/static/RexiMemo_OSE_Logo.png`. The logo is the RexiMemo mark rendered in white with “Open Source Edition” included in the image. The main web accent is `#b13b29`. Fonts are ordinary system/browser fonts; no TTF, OTF, WOFF or WOFF2 files are part of the release.

The browser layout is intentionally reminiscent of the older RexiMemo site without copying the production interface one-for-one. It uses a coloured header, compact navigation, bordered dark panels, Flipnote cards and responsive grid breakpoints.

DSi placeholder artwork is generated locally and is not copied from production artwork. Re-run `python3 tools/generate_placeholders.py` after changing the simple icon drawings or encoder.

## Tests

The test suite uses the standard library `unittest` runner:

    python3 -m unittest discover -s tests -v

`test_database.py` creates a temporary SQLite database and checks the default administrator, IP login/logout, stable guest-room ownership and IP bans.

`test_resources.py` can run even when Twisted is not installed by installing a small in-process Twisted resource/static-file stub. It changes into the repository root, builds the resource tree, checks expected DSi nodes, validates 2048-byte NTFT icons, confirms UGO resources begin with `UGAR`, renders the main web pages and verifies PNG thumbnail output. It also checks that Docs is hidden by default and renderable when a `WebRoot` is explicitly created with documentation enabled.

`test_release_shape.py` scans the checkout for blocked key/certificate/font extensions, checks that named production-only components are absent, requires exactly three sample PPMs, and checks the OSE web branding and login wording.

These tests are smoke/shape checks, not a substitute for testing on a physical DSi. The DSi resource tests verify routing and generated binary structures inside Python; they do not emulate the full Flipnote Studio browser/network stack.

> **Test-scope notice.** Passing this suite does not constitute a security review. In particular it does not prove resistance to hostile traffic, credential attacks, parser abuse, proxy misconfiguration or IP-identity edge cases. The release tests concentrate on keeping OSE small, reproducible, free of private material and compatible with the retained DSi paths.

## Changing the server

### Adding a browser page

Add a path branch to `WebRoot.render_GET()` or `render_POST()`. Use `_page()` for the shared shell. Escape any database/user-provided values with `html.escape()`, using `quote=True` for attribute values. Add CSS to `web/static/site.css`. If the page should be navigable globally, add it to `_page()`'s navigation construction.

> **Extension notice.** New authenticated, upload or moderation features should not copy assumptions from the simplified OSE identity model without considering their threat model. The repository intentionally omits production security components rather than publishing them, so an extension that needs stronger guarantees should introduce its own suitable authentication, validation, rate limiting and audit behaviour.

### Adding a DSi endpoint

For a new top-level DSi resource, place a `.py` file under `hatenadir/ds/v2-xx` and expose a `PyResource` class. The loader mounts an instance automatically at server start. For subpaths, make the resource non-leaf and return child Resource objects from `getChild()`. Keep responses simple and compatible with the DSi browser; use existing helpers for dialogs, forwarding, UGO menus and HTML wrappers.

### Adding a database field

Extend the `CREATE TABLE IF NOT EXISTS` schema and provide an upgrade path for existing SQLite files if the field cannot be added transparently. The current schema creation code creates missing tables/indexes but is not a general migration framework. Queries return rows as plain dictionaries through `_row()`.

### Adding a channel

Insert a new row in `channels`. The DSi `ch.py` resource accepts any numeric channel ID present in that table. OSE's supplied home menus still post to channel 1 unless their generated URLs are changed.

### Changing sample data

Keep SQLite records and files in `database/Creators` consistent. A Flipnote row requires the matching upper-case FSID directory and `<filename>.ppm`. The release-shape test currently expects exactly three PPM samples.

## Deliberately absent systems

OSE is not the production RexiMemo service. The public repository does not contain Nintendo NAS/DNS/auth gateway code, certificate/private-key material, production session/device management, FSID ownership proof, PPM signature verification, emulator/bot detection, passkeys, profile pictures, Creator's Room themes, experiments, Sudomemo migration, Discord integration, support-centre flows, policy/terms pages, notifications, production API tokens, web PPM upload, advanced moderation cases or the production moderation toolset.

> **Why the simplification exists.** This is a deliberate release-safety boundary. Security-sensitive production systems, secrets, trust checks and anti-abuse implementation details are excluded so publishing OSE is less likely to disclose or couple itself to RexiMemo's live infrastructure. The public replacements are intentionally smaller and easier to inspect. They exist to reduce the amount of sensitive production material exposed by an open-source release, not because a simpler login, ban or verification mechanism is inherently more secure.

The remaining code should be read with that boundary in mind. An OSE Creator's Room is an account-or-IP ownership record; a login is an IP-to-account database row; a ban is an exact IP row; browser playback is a client-side flipnote.js player with a frame-zero fallback; and the server accepts the old proxy-style DSi HTTP path rather than reproducing the removed network/authentication stack.

For public deployment work, the places most likely to need replacement or expansion are the password hashing, IP login identity, proxy/reverse-proxy IP handling, transport/authentication boundary, request-rate controls, database migrations, moderation controls, content limits/backups and operational logging. Those are outside the scope of this repository rather than hidden behind the Docs flag.
