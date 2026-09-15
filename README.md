# RexiMemo: Open Source Edition

RexiMemo OSE is a deliberately reduced public edition of the RexiMemo Flipnote Hatena replacement server. It keeps the old proxy-style DSi connection model, a SQLite database, Flipnote browsing and browser playback, posting from Flipnote Studio, Creator's Rooms, stars, downloads, web text comments, and one-frame mini Flipnote comments.

This is not a source dump of the production service. Production-only security, privacy, identity, moderation, operations, migration and community systems have been removed before release so the public repository does not expose sensitive deployment logic, credentials, private integration code or production data-handling machinery. The trade-off is important: OSE is smaller and easier to inspect, but some of its remaining mechanisms are intentionally basic and are not suitable for a hardened public service without further work.

The server does not contain Nintendo NAS, DNS interception, SSLv3/TLS gateway code or an authentication service. It listens on port 8080 and accepts the historical HTTP proxy request style used by the older public Hatena server. DSi requests to the Hatena hosts are expected to carry `X-DSi-SID`; obtaining that transport authentication is outside this repository.

## What is kept

- SQLite storage instead of the old plaintext `flipnotes.dat` database.
- The Flipnote Studio proxy resource tree and PPM/TMB/UGO/NTFT handling.
- Browse pages on DSi and web, plus a small About page listing open-source credits.
- In-browser PPM playback through flipnote.js, with play/pause, seeking, sound and loop controls plus a first-frame fallback.
- Flipnote posting from Flipnote Studio. Web PPM upload is not included.
- Creator's Rooms. A room is created automatically the first time an account or guest IP posts a Flipnote.
- Optional username/password accounts.
- Guest posting and comments tied to the source IP when no account is logged in.
- Text comments on the website and DSi, plus one-frame mini Flipnote comments from Flipnote Studio.
- A minimal web admin page for IP bans and Flipnote deletion.
- Three anonymised sample Flipnotes copied from a production database so a fresh checkout has content to browse.
- Newly generated geometric NTFT/NPF placeholder assets. The web client uses the RexiMemo logo with an Open Source Edition subtitle; other production artwork and all bundled font files are omitted.

## What is intentionally not here

RexiMemo OSE has no built-in NAS/DNS/auth gateway, certificate or private-key material, production session system, device management, FSID proof/linking, PPM signature verification, emulator or bot detection, passkeys, profile pictures, Creator's Room themes, experiments, Sudomemo migration, Discord bot/integration, support centre, policy/terms pages, notification system, API tokens, web Flipnote uploader, advanced moderation cases, or production moderation tooling.

Login state is only an `IP -> account` row in SQLite. There are no session cookies or device records. This means people sharing an IP can also share login state, and changing IPs logs a user out. Guest identity works the same way. IP addresses are stored in the database for this purpose. Bans are also intentionally simple and only block an IP address.

Passwords are stored with a simple SHA-256 digest in this reference edition. That is not modern password storage. Replace it, replace the IP login model, and add the security controls appropriate to your deployment before exposing an OSE instance to untrusted users.

## Running it

Use Python 3.10 or newer.

```sh
python3 -m pip install -r requirements.txt
python3 server.py
```

The default port is `8080`. Set `REXIMEMO_PORT` to use another port.

A detailed built-in documentation page can be enabled explicitly:

```sh
python3 server.py docs:enabled
```

With that flag, `/docs` is available and a Docs link appears in the web navigation. Without it, the route is not exposed. The same manual is also included as [`DOCS.md`](DOCS.md) for reading directly on GitHub.

Open the web client at `http://127.0.0.1:8080/`.

For Flipnote Studio on a DSi, OSE only provides the Hatena HTTP server/proxy portion. The console still needs a working authentication/NAS path. Configure the DSi to use the **official RexiMemo DNS service**, or another functional DNS/auth/NAS service, then enable **Proxy Server** in the same DSi connection and set it to the IP address of the machine running OSE with port **8080**. If `REXIMEMO_PORT` is changed, use that port instead.

This split is deliberate: authentication/NAS, private keys and the production network-security implementation are not included in OSE, reducing the risk of exposing sensitive live-service security material in the public repository. Do not add production credentials or private authentication code to the checkout.

The seeded administrator account is:

```text
username: reximemo
password: alpine
```

Change or remove that account before using the server anywhere outside a local test setup.

## Web Flipnote playback

The Flipnote view page uses **flipnote.js 6.3.1** for browser playback. The library is loaded from jsDelivr and `web/static/flipnote-player.js` provides the OSE controls and fallback behaviour. The player decodes the original PPM in the browser; OSE does not create a separate MP4, GIF or audio transcode.

Playback requests the PPM from `/media/<public id>.ppm`. That route returns the original file inline and does **not** increment the Flipnote's download counter. The **Download PPM** button continues to use `/flipnote/<public id>.ppm`, which increments the download counter and serves the file as an attachment. This keeps ordinary watch-page playback separate from an explicit file download.

If flipnote.js cannot load, the browser cannot create its playback canvas, or parsing/playback fails, the page keeps the server-generated first-frame PNG visible and disables the playback controls rather than replacing the rest of the watch page.

The flipnote.js library is currently requested from a third-party CDN, so a browser opening a watch page makes a request to jsDelivr for that JavaScript file. The PPM itself is fetched from the OSE server and is not sent to jsDelivr by this implementation. If an installation should not make third-party asset requests, host the pinned flipnote.js file locally and change the script source in `webapp.py`.

## Accounts and Creator's Rooms

Accounts are optional. Signing in associates the current source IP with an account. A Flipnote posted from that IP is attributed to the account and creates its Creator's Room if one does not exist yet. If no account is signed in, OSE creates a guest Creator's Room for the posting IP and uses the author name embedded in the Flipnote where available.

Mini Flipnote comments follow the same rule. No signed mini-Flipnote identity proof, FSID ownership verification or device-linking flow is performed in OSE.

## Database and sample content

The live database is `database/reximemo.sqlite3`. Flipnotes are stored under `database/Creators/<FSID>/` and mini comments under `database/Comments/`.

The repository ships with three sample PPM files. Their author names, FSIDs and filenames were rewritten to sample values before inclusion; the original production account, session, device, comment and moderation records are not included.

### Sample Flipnotes

The three sample files were taken from these RexiMemo Flipnotes:

- **Sample 1 — “hearts radio”** — [`f_toJRgUThEto`](https://reximemo.net/watch/f_toJRgUThEto)
- **Sample 2 — “wellinmovie: procrastination + mistakes”** — [`f_5VuKDjA4gXY`](https://reximemo.net/watch/f_5VuKDjA4gXY)
- **Sample 3 — “saddest mv you'll ever see on rexi :(”** — [`f_x6YsfDk5dkQ`](https://reximemo.net/watch/f_x6YsfDk5dkQ)

Only the Flipnote media is used as sample content. OSE replaces identifying author metadata with sample values and does not include the corresponding production account, session, device, comment or moderation records.

## Placeholder assets

`tools/generate_placeholders.py` rebuilds the DSi NTFT/NPF assets included with OSE. They are plain geometric graphics and do not reuse RexiMemo production images. The web logo is the one deliberate artwork exception and includes an Open Source Edition subtitle.

## Open-source credits

RexiMemo OSE builds on earlier Flipnote preservation and replacement-server work. The projects below are included directly or used by the server.

- **[pbsds / hatena-server](https://github.com/pbsds/hatena-server)** — AGPL-3.0. The original open-source Flipnote Hatena replacement server and the main foundation for the older public server code.
- **[Hatenatools](https://github.com/pbsds/Hatenatools)** — AGPL-3.0, pbsds and contributors. Utilities for PPM/TMB, UGO, NTFT and related Nintendo DSi and Flipnote formats. The bundled copy has been ported to Python 3.
- **[Python](https://www.python.org/)** — PSF License. The language and runtime used by RexiMemo OSE.
- **[Twisted](https://twisted.org/)** — MIT. The networking and HTTP framework used by the server.
- **[NumPy](https://numpy.org/)** — BSD-3-Clause. Used by the legacy Flipnote media and format tools.
- **[Pillow](https://python-pillow.github.io/)** — MIT-CMU. Used for image decoding and thumbnail generation.
- **[flipnote.js](https://github.com/jaames/flipnote.js)** — MIT, by James Daniel. Used for PPM animation and audio playback in the browser.

### Acknowledgements

Credit also goes to the Flipnote preservation and reverse-engineering community, including the people who documented Flipnote formats, DSi image formats, UGO menus, audio codecs and the original service's network behaviour.

The Hatenatools sources included in this repository also credit **Steven, Remark, JSAfive, Austin Burk, Midmad and WDLmaster** for format research and sample files.

RexiMemo is an independent project and is not affiliated with Nintendo or Hatena. Third-party software and names remain the property of their respective owners.

## License

RexiMemo OSE retains the GNU Affero General Public License version 3 used by the public Hatena server code. See `LICENSE` and `Hatenatools/License.txt`.
