from __future__ import annotations


def render_docs():
    """Return the built-in RexiMemo OSE repository manual."""
    return r'''
<header class="page-head docs-page-head"><div><h1>RexiMemo OSE documentation</h1><p>This manual describes the Open Source Edition as it is shipped in this repository: the HTTP server, web client, Flipnote Studio resources, SQLite layout, media handling, identity model, moderation controls, assets and tests.</p></div></header>
<div class="docs-notice"><strong>About the simplified OSE design.</strong> A number of security, identity, moderation, networking and privacy mechanisms are intentionally much simpler here than on the private RexiMemo service. This is a release-safety boundary: the open-source tree avoids exposing production keys, authentication internals, trust checks, anti-abuse logic and deployment assumptions that could create security problems for the live service if published. The simpler replacements are easier to inspect and run independently, but they should not be mistaken for stronger security. Sections with an important consequence call this out explicitly.</div>
<div class="docs-layout">
<aside class="docs-nav panel">
<div class="panel-title">Contents</div>
<nav>
<a href="#start">Starting the server</a>
<a href="#shape">Repository layout</a>
<a href="#request-routing">Request routing</a>
<a href="#web">Web client</a>
<a href="#flipnote-page">Flipnote view page</a>
<a href="#dsi">Flipnote Studio / DSi side</a>
<a href="#posting">Posting a Flipnote</a>
<a href="#comments">Comments</a>
<a href="#accounts">Accounts and IP login</a>
<a href="#rooms">Creator's Rooms</a>
<a href="#database">SQLite database</a>
<a href="#files">On-disk media</a>
<a href="#formats">PPM, TMB, UGO, NTFT and NPF</a>
<a href="#images">Image conversion code</a>
<a href="#code-reference">Internal code reference</a>
<a href="#admin">Admin and bans</a>
<a href="#configuration">Configuration</a>
<a href="#assets">Assets and styling</a>
<a href="#tests">Tests</a>
<a href="#changing">Changing the server</a>
<a href="#limits">Deliberately absent systems</a>
</nav>
</aside>
<article class="docs-content">
<section id="start" class="docs-section">
<h2>Starting the server</h2>
<p>The entry point is <code>server.py</code>. A normal start is:</p>
<pre><code>python3 -m pip install -r requirements.txt
python3 server.py</code></pre>
<p>The default TCP port is <code>8080</code>. Set <code>REXIMEMO_PORT</code> before starting the process if another port is required. The process changes its working directory to the repository root before importing the server modules, so paths such as <code>database/</code>, <code>hatenadir/</code> and <code>web/static/</code> are resolved relative to the checkout rather than the shell's current directory.</p>
<p>The optional documentation site is enabled with an argument rather than being exposed by default:</p>
<pre><code>python3 server.py docs:enabled</code></pre>
<p>When that argument is present, the server sets its documentation flag before constructing the Twisted resource tree. The web navigation gains a Docs item and <code>/docs</code> is served. Without the flag, there is no Docs navigation item and the same path follows the ordinary web 404 path.</p>
<p><code>server.py</code> creates a Twisted <code>Site</code> subclass named <code>ProxyCompatibleSite</code>. Its only protocol alteration is for old-style absolute HTTP proxy requests. Before Twisted parses incoming bytes, request lines beginning with <code>GET http://flipnote.hatena.com</code>, <code>POST http://flipnote.hatena.com</code>, <code>GET http://ugomemo.hatena.ne.jp</code> or <code>POST http://ugomemo.hatena.ne.jp</code> are rewritten into origin-form request lines. This lets the same HTTP listener accept the historical proxy traffic used by Flipnote Studio and ordinary browser requests.</p>
<div class="docs-notice"><strong>Network/security notice.</strong> OSE deliberately does not reproduce RexiMemo's production NAS, DNS, certificate or authentication gateway. Those pieces are kept out of the public repository to reduce the risk of exposing live-service security logic, secrets or deployment assumptions. As a result, OSE is only the Hatena HTTP server/proxy portion: a DSi must obtain working Nintendo/Flipnote authentication through the official RexiMemo DNS service or another functional DNS/auth/NAS setup, then send Hatena HTTP traffic to this server as its proxy.</div>
<p>Logs are written to <code>logs/reximemo.log</code> and mirrored to standard output unless a call is marked silent. The <code>logs/</code> directory is runtime data and is not part of the repository.</p>
</section>

<section id="shape" class="docs-section">
<h2>Repository layout</h2>
<table class="docs-table"><thead><tr><th>Path</th><th>Purpose</th></tr></thead><tbody>
<tr><td><code>.gitignore</code></td><td>Excludes Python caches/virtual environments, logs, SQLite WAL/SHM sidecars, common key/certificate/token files, <code>.env</code> and Finder metadata from commits.</td></tr>
<tr><td><code>server.py</code></td><td>Process entry point, port selection, optional feature flags, logging and the proxy-compatible Twisted Site.</td></tr>
<tr><td><code>hatena.py</code></td><td>Top-level HTTP resource router. It separates web traffic from DSi traffic, serves static CSS/images, loads the <code>hatenadir</code> resource tree and applies IP bans before either surface is reached.</td></tr>
<tr><td><code>reximemo.py</code></td><td>Shared DSi helpers: regional URLs, current IP/account lookup, DSi keyboard values, DSi dialog/forward headers, UGO menu construction, pagination, PPM first-frame rendering and mini-Flipnote NPF conversion.</td></tr>
<tr><td><code>webapp.py</code></td><td>The normal browser client. It renders Home, Browse, About, optional Docs, Flipnote, Creator's Room, account and admin pages and exposes thumbnails/PPM downloads.</td></tr>
<tr><td><code>docs_page.py</code></td><td>The text of this built-in manual. It is imported by the web client only when the documentation route is requested.</td></tr>
<tr><td><code>DB.py</code></td><td>Compatibility shim used by the older-style resource modules. It imports the single SQLite <code>Database</code> object and advertises <code>DB_type = "sqlite"</code>.</td></tr>
<tr><td><code>database/__init__.py</code></td><td>SQLite schema, seed data and all database operations used by the OSE server.</td></tr>
<tr><td><code>database/reximemo.sqlite3</code></td><td>Seed database supplied with the repository. It includes the default admin account, General channel, sample Creator's Rooms and three sample Flipnote records.</td></tr>
<tr><td><code>database/Creators/</code></td><td>PPM storage, grouped by creator FSID. The release contains three anonymised sample PPM files.</td></tr>
<tr><td><code>database/Comments/</code></td><td>Created/used for one-frame mini-Flipnote comment PPMs. Text comments stay entirely in SQLite.</td></tr>
<tr><td><code>hatenadir/ds/v2-xx/</code></td><td>Flipnote Studio HTTP resources. Python files are loaded into Twisted resources at start-up; the loader also supplies <code>.uls</code> aliases for <code>.ugo</code> resources.</td></tr>
<tr><td><code>hatenadir/css/ds/common.css</code></td><td>Large compatibility stylesheet containing the old DSi HTML class names expected by the retained resource layout.</td></tr>
<tr><td><code>hatenadir/css/ds/basic.css</code></td><td>Additional legacy/basic DSi styles. It overlaps a number of old service selectors but remains harmless for the small OSE page set.</td></tr>
<tr><td><code>hatenadir/css/ds/ose.css</code></td><td>Short OSE override sheet that gives the DSi HTML pages their purple/green placeholder presentation and readable detail/comment styling.</td></tr>
<tr><td><code>hatenadir/images/ds/browse.ntft</code></td><td>32×32 generated Browse menu icon.</td></tr>
<tr><td><code>hatenadir/images/ds/account.ntft</code></td><td>32×32 generated Account menu icon.</td></tr>
<tr><td><code>hatenadir/images/ds/room.ntft</code></td><td>32×32 generated Creator's Room menu icon.</td></tr>
<tr><td><code>hatenadir/images/ds/placeholder.npf</code></td><td>128×64 generated indexed placeholder banner retained for DSi asset testing/use.</td></tr>
<tr><td><code>web/static/site.css</code></td><td>Complete browser stylesheet: colour variables, header/navigation, Flipnote grids, richer watch layout, comments, forms, admin tables, documentation layout and responsive breakpoints.</td></tr>
<tr><td><code>web/static/RexiMemo_OSE_Logo.png</code></td><td>White RexiMemo logo with “Open Source Edition” included in the image itself.</td></tr>
<tr><td><code>Hatenatools/__init__.py</code></td><td>Convenience exports for <code>PPM</code>, <code>TMB</code>, <code>UGO</code> and <code>NTFT</code>.</td></tr>
<tr><td><code>Hatenatools/PPM.py</code></td><td>Legacy Flipnote Studio PPM/TMB parser: metadata, thumbnail data, frame decoding, sound decoding and helper dump functions. OSE mainly uses <code>PPM.Read()</code>, <code>PPM.GetFrame()</code> and <code>TMB.Read()</code>.</td></tr>
<tr><td><code>Hatenatools/UGO.py</code></td><td>Legacy UGO/UGAR parser/packer. OSE builds DSi menus by appending layout, top-screen text, category, post and button items then calling <code>Pack()</code>.</td></tr>
<tr><td><code>Hatenatools/NTFT.py</code></td><td>Legacy NTFT reader/writer retained for compatibility and format work. OSE's generated placeholders use the newer encoder in <code>reximemo_image_formats.py</code>.</td></tr>
<tr><td><code>Hatenatools/ReadMe.txt</code></td><td>Original Hatenatools version notes, format summary and contributor credits.</td></tr>
<tr><td><code>Hatenatools/License.txt</code></td><td>The Hatenatools AGPL licence text shipped with that code.</td></tr>
<tr><td><code>Hatenatools/hatenatools project page.url</code></td><td>Legacy Internet Shortcut retained with the upstream helper sources.</td></tr>
<tr><td><code>reximemo_image_formats.py</code></td><td>Independent image codec helpers for NTFT, NPF and NBF plus standard Pillow-backed image formats.</td></tr>
<tr><td><code>tools/generate_placeholders.py</code></td><td>Rebuilds the plain DSi placeholder icons and banner from simple geometric shapes.</td></tr>
<tr><td><code>tests/test_database.py</code></td><td>Temporary-database checks for seed admin, IP login/logout, guest room stability and bans.</td></tr>
<tr><td><code>tests/test_resources.py</code></td><td>Twisted-stub resource tests covering the DSi tree, UGAR menu generation, web routes, watch-page detail, Docs gating and PNG thumbnail generation.</td></tr>
<tr><td><code>tests/test_release_shape.py</code></td><td>Release checks preventing key/certificate/font file types, named removed production components and sample-content drift.</td></tr>
<tr><td><code>requirements.txt</code></td><td>Runtime Python dependencies: Twisted, NumPy and Pillow.</td></tr>
<tr><td><code>README.md</code></td><td>Short installation/release overview.</td></tr>
<tr><td><code>DOCS.md</code></td><td>GitHub-readable copy of this detailed technical reference. The built-in <code>/docs</code> page and this file are intended to carry the same operational information.</td></tr>
<tr><td><code>LICENSE</code></td><td>GNU Affero General Public License version 3.</td></tr>
</tbody></table>
<p>The three sample PPM paths are <code>database/Creators/A000000000000001/000001_OSEOPEN000001_000.ppm</code>, <code>...0002/000002_OSEOPEN000002_001.ppm</code> and <code>...0003/000003_OSEOPEN000003_002.ppm</code>. Their matching public Flipnote IDs are <code>f_sample1</code> through <code>f_sample3</code>; their Creator's Room public IDs are <code>r_sample1</code> through <code>r_sample3</code>.</p>
</section>

<section id="request-routing" class="docs-section">
<h2>Request routing</h2>
<p><code>hatena.Setup()</code> returns a <code>Root</code> resource. Every request first reaches that object. The source IP is checked against <code>ip_bans</code> before web or DSi routing. A blocked address receives a plain <code>403</code> response.</p>
<p>The request's <code>Host</code> header determines which surface is selected. <code>flipnote.hatena.com</code> and <code>ugomemo.hatena.ne.jp</code> are treated as DSi hosts. Everything else, including <code>localhost</code> and a normal server hostname, is sent to <code>WebRoot</code>.</p>
<p>DSi-host requests must contain <code>X-DSi-SID</code>. OSE does not validate or decode the SID; the header is only the transport-side gate expected by this reduced resource tree. A missing header produces the access-denied resource. This is deliberately separate from account state: an IP may have a web/DSi OSE account login row while DSi-host routing still requires the header.</p>
<div class="docs-notice"><strong>Identity notice.</strong> <code>X-DSi-SID</code> is a compatibility marker in OSE, not proof of a particular console or account. Production SID/device verification, FSID ownership checks and related anti-abuse systems were intentionally removed rather than publishing their implementation. This keeps the public DSi path small, but callers must not treat the header as a security credential.</div>
<p>Static top-level routes are handled before host routing. <code>/css/</code> maps to <code>hatenadir/css/</code>, <code>/images/</code> maps to <code>hatenadir/images/</code>, and <code>/static/</code> maps to <code>web/static/</code>. This mirrors the old server shape while keeping browser assets separate from DSi assets.</p>
<p>The DSi region root recognises <code>v2-xx</code>, <code>v2-eu</code>, <code>v2-us</code> and <code>v2-jp</code>. All four currently use the same loaded <code>v2-xx</code> implementation. URL generation switches the Japanese host to <code>ugomemo.hatena.ne.jp</code>; the other regions use <code>flipnote.hatena.com</code>.</p>
</section>

<section id="web" class="docs-section">
<h2>Web client</h2>
<p>The browser client is server-rendered HTML in <code>webapp.py</code>. It has no JavaScript framework and no browser session cookie. Each request asks the database for the account currently associated with the source IP.</p>
<div class="docs-notice"><strong>Login notice.</strong> The web client uses the same deliberately simple IP identity model as the rest of OSE. Production session/device management was left out so that live authentication design, keys and account-security machinery are not copied into a public release. Shared addresses, proxies and changing IPs therefore have consequences described in the Accounts section below.</div>
<table class="docs-table"><thead><tr><th>Route</th><th>Method</th><th>Behaviour</th></tr></thead><tbody>
<tr><td><code>/</code></td><td>GET</td><td>Home page with the most recent Flipnotes.</td></tr>
<tr><td><code>/browse</code></td><td>GET</td><td>Browse up to 100 Flipnotes. <code>?sort=new</code>, <code>?sort=popular</code> and <code>?sort=top</code> map to posted time, views/stars and stars/views orderings.</td></tr>
<tr><td><code>/about</code></td><td>GET</td><td>Open-source credits and acknowledgements only.</td></tr>
<tr><td><code>/docs</code></td><td>GET</td><td>This manual, only when documentation is enabled at server start.</td></tr>
<tr><td><code>/watch/&lt;public id&gt;</code></td><td>GET</td><td>Flipnote detail page. It increments the view count, loads comments and shows other notes from the same Creator's Room.</td></tr>
<tr><td><code>/watch/&lt;public id&gt;/comment</code></td><td>POST</td><td>Adds a text comment using the current account or guest-IP Creator's Room.</td></tr>
<tr><td><code>/thumb/&lt;public id&gt;.png</code></td><td>GET</td><td>Decodes the first PPM frame and returns a cached PNG thumbnail.</td></tr>
<tr><td><code>/comment-thumb/&lt;id&gt;.png</code></td><td>GET</td><td>Returns a first-frame PNG preview for a mini-Flipnote comment.</td></tr>
<tr><td><code>/flipnote/&lt;public id&gt;.ppm</code></td><td>GET</td><td>Increments downloads and returns the original PPM as an attachment.</td></tr>
<tr><td><code>/creator/&lt;public id&gt;</code></td><td>GET</td><td>Creator's Room with its Flipnote grid and account/guest ownership label.</td></tr>
<tr><td><code>/login</code></td><td>GET/POST</td><td>Username/password sign-in. Successful POST writes an <code>ip_logins</code> row for the source IP.</td></tr>
<tr><td><code>/register</code></td><td>GET/POST</td><td>Creates an account and immediately associates the source IP with it.</td></tr>
<tr><td><code>/logout</code></td><td>GET</td><td>Deletes the current source IP from <code>ip_logins</code>.</td></tr>
<tr><td><code>/account</code></td><td>GET</td><td>Shows the signed-in username, current IP and Creator's Room link when one exists.</td></tr>
<tr><td><code>/admin</code></td><td>GET</td><td>Minimal administrator view for IP bans and Flipnote deletion.</td></tr>
<tr><td><code>/admin/ban</code></td><td>POST</td><td>Adds or updates an IP ban and clears that IP's login row.</td></tr>
<tr><td><code>/admin/unban</code></td><td>POST</td><td>Removes an IP ban.</td></tr>
<tr><td><code>/admin/delete</code></td><td>POST</td><td>Soft-deletes a Flipnote record by setting <code>deleted=1</code>.</td></tr>
</tbody></table>
<p>The common page wrapper builds the header, navigation, account/admin actions and footer. Docs is inserted into that navigation only when the <code>WebRoot</code> instance was created with documentation enabled.</p>
</section>

<section id="flipnote-page" class="docs-section">
<h2>Flipnote view page</h2>
<p>The browser does not attempt to reproduce Flipnote Studio playback. A Flipnote view uses the first decoded frame as a large preview and presents the original <code>.ppm</code> as the downloadable playable file. This keeps the web client small and avoids adding a separate animation/audio player implementation.</p>
<p>Opening the page calls <code>Database.AddView()</code> before the Flipnote row is reloaded, so the displayed view count includes the current request. The page then loads up to 100 comments, the channel record, the Creator's Room record and a short list of other non-deleted Flipnotes from the same room.</p>
<p>The information panel displays stars, views, downloads and comment count, then the post time, channel, creator FSID, PPM filename and public identifier. These values come directly from the OSE SQLite row; there is no secondary profile, device or ownership lookup.</p>
<div class="docs-notice"><strong>Metadata notice.</strong> Creator metadata shown here is repository data, not a cryptographically verified identity. OSE deliberately avoids the production ownership/device verification chain so those security mechanisms are not exposed in the public codebase. Treat FSIDs, embedded creator names and room ownership as local OSE identifiers.</div>
<p>Text comments are HTML-escaped. Mini-Flipnote comments are shown as first-frame thumbnails through <code>/comment-thumb/&lt;id&gt;.png</code>; the stored PPM is still the authoritative comment file used by the DSi endpoints.</p>
</section>

<section id="dsi" class="docs-section">
<h2>Flipnote Studio / DSi side</h2>
<h3>Connecting a DSi</h3>
<p>RexiMemo OSE does not contain the authentication/NAS or DNS service needed to get a DSi through the normal Nintendo/Flipnote connection path. Use the official RexiMemo DNS service, or another working DNS setup that also provides the required authentication/NAS behaviour for Flipnote Studio.</p>
<ol class="docs-steps">
<li>Configure the DSi internet connection to use the official RexiMemo DNS service, or another known-working DNS/auth/NAS service.</li>
<li>In the same DSi connection settings, enable the HTTP <strong>Proxy Server</strong>.</li>
<li>Set the proxy server address to the IP address of the machine running RexiMemo OSE.</li>
<li>Set the proxy port to <code>8080</code>, unless <code>REXIMEMO_PORT</code> was deliberately changed on the OSE server.</li>
<li>Start OSE with <code>python3 server.py</code> and then open Flipnote Studio/Flipnote Hatena on the DSi.</li>
</ol>
<p>DNS/auth/NAS and the Hatena HTTP proxy are separate jobs in this arrangement. The external DNS/auth/NAS service gets the console through the authentication path; RexiMemo OSE handles the Hatena web requests that the DSi sends to the configured proxy.</p>
<div class="docs-notice"><strong>Connection/security notice.</strong> The missing auth/NAS stack is deliberate. OSE uses an external working service instead of publishing RexiMemo's private authentication and network-security implementation. Do not copy private keys, production credentials or live authentication code into an OSE checkout to make up for the missing component. Point the DSi at an authorised working DNS/auth/NAS service and keep OSE limited to the proxy/server role it was released for.</div>
<p>The DSi surface is built from Twisted resources under <code>hatenadir/ds/v2-xx</code>. <code>hatena.LoadHatenadirStructure()</code> walks that directory at start-up. Ordinary files become static resources. A filename ending in <code>.py</code> is imported as a module and its <code>PyResource()</code> object is mounted under the filename without <code>.py</code>. Any resulting resource whose mounted name ends in <code>.ugo</code> is also mounted under the equivalent <code>.uls</code> name.</p>
<table class="docs-table"><thead><tr><th>Resource</th><th>Function</th></tr></thead><tbody>
<tr><td><code>index.ugo.py</code></td><td>Home UGO menu. It shows Browse, Account, the current Creator's Room when one exists, then recent Flipnotes. Menu icons are the generated 32×32 NTFT placeholders.</td></tr>
<tr><td><code>allflipnotes.ugo.py</code></td><td>Paginated all-Flipnotes UGO list. It uses 50 Flipnotes per page and adds Previous/Next buttons when required.</td></tr>
<tr><td><code>ch.py</code></td><td>Channel browse and posting. <code>ch/1.uls</code> lists channel Flipnotes; <code>ch/1.htm</code> is a small HTML description; POST to <code>ch/1.post</code> accepts a PPM and stores it.</td></tr>
<tr><td><code>creator.py</code></td><td>Creator's Room resources. It accepts the numeric internal room ID and serves <code>profile.htm</code>, <code>room.uls</code> and <code>movies.uls</code>. <code>room.ugo</code>/<code>movies.ugo</code> are accepted as aliases.</td></tr>
<tr><td><code>movie.py</code></td><td>Flipnote PPM/TMB/details, star, download and comment endpoints.</td></tr>
<tr><td><code>comment.py</code></td><td>Stored mini-Flipnote comment delivery as raw <code>.ppm</code> or generated <code>.npf</code> preview.</td></tr>
<tr><td><code>sa.py</code></td><td>Simple DSi account pages and keyboard-based login/register/logout flow.</td></tr>
<tr><td><code>inbox.ugo.py</code></td><td>Empty compatibility page stating that notifications are not included.</td></tr>
<tr><td><code>eula_list.tsv</code></td><td>Static compatibility row containing the base64-encoded “English” label and <code>en</code> language code. It is retained because older clients/resources may request the file even though OSE has no terms/EULA flow.</td></tr>
</tbody></table>
<p>UGO menu data is assembled by <code>reximemo.make_menu()</code> through Hatenatools' <code>UGO</code> class. Thumbnail buttons embed the first <code>0x6A0</code> bytes of a PPM as TMB data. Icon buttons embed a 32×32 NTFT and are rejected if the byte length is not exactly 2048.</p>
<p>The DSi HTML helper links <code>common.css</code>, <code>basic.css</code> and <code>ose.css</code> from the Hatena host. These pages deliberately stay small and old-browser friendly: basic HTML, tables, metadata tags and CSS with no JavaScript dependency.</p>
</section>

<section id="posting" class="docs-section">
<h2>Posting a Flipnote</h2>
<ol class="docs-steps">
<li>Flipnote Studio POSTs PPM bytes to a channel <code>.post</code> resource.</li>
<li><code>ch.py</code> reads the request body and asks <code>current_account()</code> whether the source IP is signed in.</li>
<li><code>Database.AddFlipnote()</code> parses the PPM header through Hatenatools <code>TMB().Read()</code>.</li>
<li>The editor author ID becomes the stored creator FSID. <code>CurrentFilename</code> supplies the base filename. If either value is missing, or the same FSID/filename already exists, the post is refused.</li>
<li>The embedded username/editor name is used as the display-name hint.</li>
<li><code>get_or_create_creator()</code> obtains the account-owned room or guest-IP room. This is the point at which a Creator's Room is automatically created for a first post.</li>
<li>The requested channel is checked; an unknown channel falls back to channel 1.</li>
<li>A Flipnote row is created with a new public ID beginning <code>f_</code>.</li>
<li>The exact submitted PPM bytes are written to <code>database/Creators/&lt;FSID&gt;/&lt;filename&gt;.ppm</code>.</li>
</ol>
<p>No web PPM upload route exists. Browser users can browse/download/comment, but new Flipnotes enter OSE through the Flipnote Studio channel post path.</p>
<div class="docs-notice"><strong>Posting notice.</strong> OSE reads the creator FSID, username and filename from the submitted PPM, but it does not perform the production FSID ownership or PPM signature-verification steps. Those systems were removed to avoid releasing production trust logic and key-dependent verification code. The simpler OSE path is intended for a small self-hosted/test environment; do not interpret embedded PPM identity fields as independently proven.</div>
</section>

<section id="comments" class="docs-section">
<h2>Comments</h2>
<h3>Text comments</h3>
<p>Web text comments POST a normal form field named <code>text</code>. DSi text comments use the keyboard endpoint and read the value from <code>X-Email-Addr</code>, matching the old keyboard transport convention. The database collapses whitespace, truncates to 500 characters and rejects an empty result.</p>
<p>A comment needs a Creator's Room. If the source IP is logged in, the room belongs to that account. Otherwise a room is created or reused for the source IP. The stored comment references only the room ID; display names shown later are joined from <code>creator_rooms</code>.</p>
<h3>Mini-Flipnote comments</h3>
<p>A POST to a Flipnote's <code>.reply</code> endpoint is parsed as PPM/TMB. OSE requires exactly one frame. The PPM's author ID and embedded username are passed into the same room-creation function, then the comment row is inserted as type <code>memo</code>. Its binary PPM is written to <code>database/Comments/&lt;comment id&gt;.ppm</code> and that filename is stored in the row.</p>
<p>For the DSi comment preview, <code>comment_npf()</code> decodes the first PPM frame, resizes it to the requested dimensions and encodes it as NPF. Width is clamped to 1–256 and height to 1–192. The raw mini-Flipnote remains available through its <code>.ppm</code> comment route.</p>
<div class="docs-notice"><strong>Comment identity notice.</strong> Guest comments are attached to an IP-backed Creator's Room, and mini-Flipnote identity hints come from the submitted PPM. This is intentionally simpler than production moderation/account attribution so the public tree does not contain the production device, session and ownership-verification stack. On shared networks, more than one person can therefore appear under the same guest identity.</div>
</section>

<section id="accounts" class="docs-section">
<h2>Accounts and IP login</h2>
<p>Accounts are optional. Usernames are 3–24 characters and may contain ASCII letters, numbers, dots, dashes and underscores. Passwords must contain at least four characters. The OSE database stores a SHA-256 digest in <code>password_sha256</code>.</p>
<div class="docs-notice"><strong>Account security notice.</strong> Accounts are deliberately implemented in a much simpler form than the private service. Production password/session/device security, passkeys, recovery flows, per-device state and authentication-gateway logic are not published here because doing so could expose security-sensitive implementation details or assumptions from the live service. OSE substitutes a small local model so the public code can stand alone. That release choice limits what sensitive production material is exposed; it does not make the replacement stronger. Unsalted SHA-256 is not a modern password-storage scheme and the minimum password rule is intentionally small.</div>
<p>OSE login state is tied to your IP address. <code>login_ip()</code> upserts one <code>ip_logins</code> row whose primary key is the source IP. If that address logs into a different account, the row is replaced with the new account ID. <code>account_for_ip()</code> joins the row to <code>accounts</code> and refreshes <code>last_seen</code>. Logout deletes the row.</p>
<p>There are no cookies or browser session identifiers in this flow. The DSi and browser clients see the same account when they reach the server from the same source IP. If traffic is behind a shared NAT or reverse proxy, the address visible to Twisted is the identity key used by OSE.</p>
<div class="docs-notice"><strong>IP login notice.</strong> An IP address is only a convenient OSE ownership key. Addresses can be shared, reassigned, hidden behind NAT or represented by a reverse proxy. OSE uses this simpler local mapping so the public release does not contain RexiMemo's production session/device security implementation, reducing the risk of exposing live-service authentication behaviour. It is a release-safety compromise, not a secure substitute for a proper session design.</div>
<p>The DSi account page uses <code>username:password</code> entered through the Flipnote Studio keyboard. The keyboard value arrives in <code>X-Email-Addr</code>. Registration creates the account, writes the IP login, and forwards back to <code>sa/account.htm</code> using <code>X-DSi-Forwarder</code>.</p>
<p>The seeded administrator is <code>reximemo</code> with password <code>alpine</code>. It is created only when no account named <code>reximemo</code> exists in the opened database.</p>
<div class="docs-notice"><strong>Default credential notice.</strong> The seed login exists so a fresh checkout can exercise the admin page immediately. It is public repository data, not a secret. Change or remove it before exposing an OSE instance beyond a controlled test network.</div>
</section>

<section id="rooms" class="docs-section">
<h2>Creator's Rooms</h2>
<p>A room has an internal integer ID and a public ID beginning <code>r_</code>. Account rooms have <code>account_id</code> set and normally have no <code>owner_ip</code>. Guest rooms have <code>owner_ip</code> set and no account ID. SQLite uniqueness rules permit only one room per account and one guest room per stored IP.</p>
<p>For an account, the displayed room name is the account username. A first observed FSID can fill an empty room FSID. For a guest, the first room name is either the PPM-provided creator name or a deterministic <code>Guest-XXXXXX</code> value derived from the IP with SHA-1. If a guest room still has the generated Guest name, a later PPM with a display name can replace it.</p>
<p>The web uses the room's public ID in URLs. The DSi resource tree primarily uses the internal numeric room ID for Creator's Room paths. <code>UgoRoot</code> also recognises a 16-hex-character path component and can resolve a room from its FSID before passing into the creator resource.</p>
<div class="docs-notice"><strong>Room ownership notice.</strong> Account ownership and guest-IP ownership are convenience rules inside this OSE database. They do not reproduce production creator verification. This design deliberately avoids carrying production account/device linkage and FSID proof into the public repository, so room ownership should be understood as local OSE state rather than an authoritative Nintendo/Flipnote identity claim.</div>
</section>

<section id="database" class="docs-section">
<h2>SQLite database</h2>
<p><code>DatabaseBackend</code> opens <code>database/reximemo.sqlite3</code> unless <code>REXIMEMO_DB</code> points elsewhere. <code>check_same_thread=False</code> is used because Twisted/resource code may access the shared connection outside SQLite's default creating-thread check. A re-entrant Python lock wraps writes and related grouped operations. Foreign keys are enabled and journal mode is set to WAL.</p>
<table class="docs-table"><thead><tr><th>Table</th><th>Important fields</th><th>Meaning</th></tr></thead><tbody>
<tr><td><code>accounts</code></td><td><code>username</code>, <code>password_sha256</code>, <code>is_admin</code>, <code>created_at</code></td><td>Optional local web/DSi account.</td></tr>
<tr><td><code>ip_logins</code></td><td><code>ip</code> primary key, <code>account_id</code>, <code>last_seen</code></td><td>Current IP-to-account association.</td></tr>
<tr><td><code>ip_bans</code></td><td><code>ip</code> primary key, <code>reason</code>, <code>created_at</code></td><td>Addresses denied before routing.</td></tr>
<tr><td><code>creator_rooms</code></td><td><code>public_id</code>, <code>account_id</code>, <code>owner_ip</code>, <code>fsid</code>, <code>display_name</code></td><td>Identity/ownership container used by Flipnotes and comments.</td></tr>
<tr><td><code>channels</code></td><td><code>id</code>, <code>title</code>, <code>description</code></td><td>Posting/browse channel. OSE seeds channel 1 as General.</td></tr>
<tr><td><code>flipnotes</code></td><td><code>public_id</code>, room, FSID, filename, title, channel, counters, <code>posted_at</code>, <code>deleted</code></td><td>Metadata for each stored PPM.</td></tr>
<tr><td><code>comments</code></td><td><code>public_id</code>, Flipnote, room, <code>type</code>, text/memo filename, <code>posted_at</code>, <code>deleted</code></td><td>Text or one-frame mini-Flipnote comments.</td></tr>
</tbody></table>
<p><code>flipnotes</code> has a uniqueness constraint on <code>(creator_fsid, filename)</code>. Public IDs are generated from <code>secrets.token_urlsafe()</code>, stripped of <code>-</code>/<code>_</code>, truncated, and prefixed according to object type. They are routing identifiers rather than authentication tokens.</p>
<div class="docs-notice"><strong>Database/privacy notice.</strong> OSE stores usernames, password digests, source IP login mappings, guest owner IPs and IP bans directly in SQLite. This is deliberately straightforward so the public release has no hidden account/session service or production datastore dependency. If you run a public instance, decide what IP retention, access control, backups and database-file permissions are appropriate for your environment.</div>
<p>Flipnote deletion is a soft delete. Listing and lookup queries require <code>deleted=0</code>; the PPM file is not erased by <code>delete_flipnote()</code>. Comments also carry a <code>deleted</code> column, although the OSE web admin does not expose comment moderation controls.</p>
<p>Sorting rules are defined in <code>list_flipnotes()</code>. Newest uses <code>posted_at DESC, id DESC</code>; Popular uses views, then stars, then posted time; Stars uses stars, then views, then posted time.</p>
</section>

<section id="files" class="docs-section">
<h2>On-disk media</h2>
<p>SQLite holds metadata; PPM bytes are kept as files. A Flipnote path is constructed as:</p>
<pre><code>database/Creators/&lt;upper-case FSID&gt;/&lt;filename&gt;.ppm</code></pre>
<p>The PPM filename stored in SQLite does not include <code>.ppm</code>. <code>GetFlipnotePPM()</code> reads the whole file. <code>GetFlipnoteTMB()</code> reads only the first <code>0x6A0</code> bytes for menu thumbnails.</p>
<p>Mini comments use:</p>
<pre><code>database/Comments/&lt;numeric comment id&gt;.ppm</code></pre>
<p>The database stores that basename in <code>memo_filename</code>. The numeric filename is assigned after the row insert because the SQLite row ID is used as the stable file name.</p>
<p>The release's three example PPMs use sample FSIDs and rewritten sample metadata. They are present so the web/DSi browse paths, thumbnail decoder and download routes can be tested immediately after cloning.</p>
<div class="docs-notice"><strong>Storage notice.</strong> Flipnotes and mini-Flipnote comments are ordinary files on disk and are not encrypted by OSE. A soft-deleted Flipnote row also leaves its PPM file in place. The storage model is intentionally transparent and dependency-free; operators who need stronger deletion, encryption, retention or backup guarantees should add them outside or on top of this repository.</div>
</section>

<section id="formats" class="docs-section">
<h2>PPM, TMB, UGO, NTFT and NPF</h2>
<h3>PPM and TMB</h3>
<p>PPM is the Flipnote Studio animation container handled by <code>Hatenatools/PPM.py</code>. OSE uses the full PPM parser when it needs a decoded frame or mini-Flipnote validation. It uses <code>TMB().Read()</code> for metadata-oriented work such as FSID, username, filename and frame count. For menu thumbnails the first <code>0x6A0</code> bytes are served directly as TMB data.</p>
<div class="docs-notice"><strong>Parser notice.</strong> Hatenatools is retained primarily for compatibility with these old file formats. OSE deliberately does not wrap it in the full set of production upload validation, signature checks, anti-abuse controls and isolation measures. Treat arbitrary files from an untrusted public upload source as untrusted input and add the controls suitable for that deployment.</div>
<p><code>ppm_first_frame_image()</code> asks Hatenatools to read frames but not sound, obtains frame zero, converts the returned array in Fortran order and constructs a Pillow RGBA image. Browser thumbnails convert that image to RGB and resize with nearest-neighbour resampling.</p>
<h3>UGO / UGAR</h3>
<p>Flipnote Studio menu screens are packed with Hatenatools <code>UGO</code>. <code>make_menu()</code> begins with a layout item, optionally adds top-screen title data and category/dropdown items, then encodes each button. Flipnote buttons embed TMB thumbnails; OSE navigation buttons embed generated NTFT icons. The packed result begins with the UGAR container signature used by the test suite.</p>
<h3>NTFT</h3>
<p>NTFT assets are raw 16-bit ABGR1555 pixels. Dimensions are external to the file. A 32×32 NTFT therefore occupies exactly 2048 bytes. The OSE UGO helper enforces that size for embedded menu icons.</p>
<h3>NPF</h3>
<p>NPF is a 4-bit indexed image format with a transparent index and up to 15 opaque colours. OSE uses it for mini-Flipnote comment previews and one generated placeholder banner. Width and height are supplied by the caller because the raw image dimensions are not stored in the NPF payload.</p>
<h3>NBF</h3>
<p><code>reximemo_image_formats.py</code> also retains NBF encode/decode support. NBF is an 8-bit indexed format with up to 256 opaque colours. There is no current OSE HTTP endpoint that requires NBF; the codec remains useful for working with related DSi assets.</p>
</section>

<section id="images" class="docs-section">
<h2>Image conversion code</h2>
<p><code>reximemo_image_formats.py</code> is a self-contained converter for Nintendo-oriented and standard still-image formats. The proprietary set is <code>ntft</code>, <code>npf</code> and <code>nbf</code>. Standard outputs are PNG, JPEG, WebP, BMP and GIF.</p>
<p>Input dimensions are validated before large allocations: each side is limited to 2048 pixels and total area to 4,194,304 pixels. Raw formats whose dimensions are not embedded require width/height from the caller. ABGR1555 packing/unpacking is implemented directly. Indexed formats use Pillow quantisation after conversion to a reduced 5-bit colour space, which better matches the source pixel formats.</p>
<p>The public encoder returns an <code>EncodedImage</code> dataclass containing bytes, format key/label, extension, MIME type, preview image and format note. The decoder returns a <code>DecodedImage</code> with the corresponding image and metadata. JPEG/BMP paths flatten transparency onto white; GIF output is one still frame.</p>
<p><code>tools/generate_placeholders.py</code> uses this encoder. It draws three 32×32 icons and one 128×64 banner with Pillow primitives and writes NTFT/NPF bytes into <code>hatenadir/images/ds</code>.</p>
</section>

<section id="code-reference" class="docs-section">
<h2>Internal code reference</h2>
<p>This section lists the small internal API that joins the repository together. Names are included because most extensions to OSE can be made by following these existing call paths rather than adding another framework layer.</p>
<h3><code>hatena.py</code></h3>
<table class="docs-table"><thead><tr><th>Name</th><th>Role</th></tr></thead><tbody>
<tr><td><code>as_text(value)</code></td><td>Converts bytes to UTF-8 text with replacement for malformed sequences; all other values are stringified.</td></tr>
<tr><td><code>request_path(request)</code></td><td>Returns the request path as text.</td></tr>
<tr><td><code>request_headers(request)</code></td><td>Builds a lower-case text-keyed dictionary from Twisted's request headers.</td></tr>
<tr><td><code>request_args(request)</code></td><td>Converts Twisted's byte query arguments into a text dictionary whose values remain lists.</td></tr>
<tr><td><code>client_ip(request)</code></td><td>Reads <code>getClientIP()</code> first and falls back to <code>getClientAddress().host</code>. The returned string is the key used by OSE login, guest ownership and bans.</td></tr>
<tr><td><code>Log(request, path=None, silent=...)</code></td><td>Writes a short source-IP/request-path entry through the process logger when one is attached.</td></tr>
<tr><td><code>AccessDeniedResource</code></td><td>Plain 403 used when DSi-host traffic does not carry <code>X-DSi-SID</code>.</td></tr>
<tr><td><code>BannedResource</code></td><td>Plain 403 used for an IP present in <code>ip_bans</code>.</td></tr>
<tr><td><code>NotFoundResource</code></td><td>Plain 404 resource which also records the path/query in the log.</td></tr>
<tr><td><code>Root</code></td><td>Top-level static/host router. It owns the web root, DSi root and static directory resources.</td></tr>
<tr><td><code>DSRoot</code></td><td>Recognises supported <code>v2-*</code> region names and forwards each to the shared UgoRoot.</td></tr>
<tr><td><code>UgoRoot</code></td><td>Loads <code>hatenadir/ds/v2-xx</code>. It also resolves a bare 16-hex FSID path to a Creator's Room when possible.</td></tr>
<tr><td><code>FileResource</code></td><td>Static DSi file wrapper. Files whose extension starts with <code>htm</code> receive an HTML content type.</td></tr>
<tr><td><code>FolderResource</code></td><td>Container for recursively loaded directories. Direct rendering is forbidden with 403.</td></tr>
<tr><td><code>LoadHatenadirStructure()</code></td><td>One-level-at-a-time recursive loader. Python resources are imported by absolute path with a SHA-1-derived module name to avoid ordinary module-name collisions.</td></tr>
<tr><td><code>Setup(docs_enabled=False)</code></td><td>Constructs the root resource and passes the documentation switch into the browser <code>WebRoot</code>.</td></tr>
</tbody></table>

<h3><code>reximemo.py</code></h3>
<table class="docs-table"><thead><tr><th>Name</th><th>Role</th></tr></thead><tbody>
<tr><td><code>region_from_request()</code></td><td>Finds the first path segment beginning <code>v2-</code> and returns its region suffix; defaults to <code>xx</code>.</td></tr>
<tr><td><code>host_for_region()</code></td><td>Returns the Japanese Ugomemo host for <code>jp</code>, otherwise the main Flipnote host.</td></tr>
<tr><td><code>dsi_url()</code></td><td>Builds an absolute historical-style DSi URL using the current request region.</td></tr>
<tr><td><code>current_account()</code></td><td>Looks up the source IP in <code>ip_logins</code>.</td></tr>
<tr><td><code>current_creator()</code></td><td>Convenience call into <code>get_or_create_creator()</code> using the request IP/current account and optional PPM identity hints.</td></tr>
<tr><td><code>keyboard_value()</code></td><td>Returns the stripped <code>X-Email-Addr</code> header used by Flipnote Studio keyboard submissions.</td></tr>
<tr><td><code>dialog()</code></td><td>Sets an HTTP status, <code>X-DSi-Dialog-Type: 1</code>, plain content type and UTF-16LE message body.</td></tr>
<tr><td><code>forward()</code></td><td>Sets <code>X-DSi-Forwarder</code> to tell the DSi browser which resource to open next.</td></tr>
<tr><td><code>html_page()</code></td><td>Produces the minimal DSi HTML wrapper, top-screen title metadata and three DSi stylesheets.</td></tr>
<tr><td><code>query_int()</code></td><td>Reads a query argument as an integer and clamps it to caller-supplied minimum/maximum bounds.</td></tr>
<tr><td><code>make_menu()</code></td><td>Builds an in-memory UGO menu from layout/title/category/post/button dictionaries, including embedded TMB or NTFT data.</td></tr>
<tr><td><code>placeholder_icon()</code></td><td>Reads one generated NTFT file from <code>hatenadir/images/ds</code>.</td></tr>
<tr><td><code>flipnote_buttons()</code></td><td>Turns database Flipnote rows into UGO thumbnail buttons; unreadable PPM/TMB files are skipped.</td></tr>
<tr><td><code>pagination_buttons()</code></td><td>Calculates page count and returns Previous/Next UGO button dictionaries.</td></tr>
<tr><td><code>ppm_first_frame_image()</code></td><td>Decodes PPM frame zero into a Pillow RGBA image.</td></tr>
<tr><td><code>ppm_thumbnail_png()</code></td><td>Creates a nearest-neighbour RGB PNG thumbnail from frame zero.</td></tr>
<tr><td><code>comment_npf()</code></td><td>Loads a stored mini-comment PPM, decodes/resizes its first frame and returns NPF bytes.</td></tr>
</tbody></table>

<h3><code>DatabaseBackend</code></h3>
<div class="docs-notice"><strong>Implementation notice.</strong> Several database methods below deal with login, ownership and moderation. Their small size is intentional: the OSE implementation replaces production session/device/security services with local SQLite operations so private operational logic is not exposed. Method names such as <code>verify_account()</code> describe what they do inside OSE, not a claim that they provide production-grade identity verification.</div>
<table class="docs-table"><thead><tr><th>Method/property</th><th>Role</th></tr></thead><tbody>
<tr><td><code>create_account()</code></td><td>Validates username/password, hashes the password and inserts a non-admin account.</td></tr>
<tr><td><code>verify_account()</code></td><td>Hashes the supplied password and queries by username plus digest.</td></tr>
<tr><td><code>get_account()</code> / <code>get_account_by_username()</code></td><td>Direct account lookup helpers.</td></tr>
<tr><td><code>login_ip()</code></td><td>Upserts the one login row for an IP and records <code>last_seen</code>.</td></tr>
<tr><td><code>logout_ip()</code></td><td>Deletes an IP login row.</td></tr>
<tr><td><code>account_for_ip()</code></td><td>Joins login to account and refreshes <code>last_seen</code> when found.</td></tr>
<tr><td><code>is_ip_banned()</code>, <code>ban_ip()</code>, <code>unban_ip()</code>, <code>list_bans()</code></td><td>Exact-IP moderation operations. Banning also signs that IP out.</td></tr>
<tr><td><code>get_creator_room*</code></td><td>Room lookups by numeric ID, public ID or FSID.</td></tr>
<tr><td><code>room_for_account()</code> / <code>room_for_ip()</code></td><td>Ownership lookups used before automatic room creation.</td></tr>
<tr><td><code>get_or_create_creator()</code></td><td>Central account/guest identity resolver. It creates the room on first use and fills previously empty FSID/name fields when suitable.</td></tr>
<tr><td><code>list_creator_flipnotes()</code></td><td>Thin room-filtered wrapper around <code>list_flipnotes()</code>.</td></tr>
<tr><td><code>get_channel()</code> / <code>list_channels()</code></td><td>Channel metadata access.</td></tr>
<tr><td><code>FlipnotePath()</code></td><td>Returns the PPM filesystem path for an FSID/filename pair.</td></tr>
<tr><td><code>CreatorExists()</code></td><td>True when a room with the FSID exists or the corresponding creator directory exists.</td></tr>
<tr><td><code>FlipnoteExists()</code></td><td>Requires both a non-deleted database row and an existing PPM file.</td></tr>
<tr><td><code>AddFlipnote()</code></td><td>Parses TMB identity/filename, resolves the room/channel, inserts metadata and writes PPM bytes.</td></tr>
<tr><td><code>get_flipnote()</code>, <code>get_flipnote_by_id()</code>, <code>get_flipnote_by_public_id()</code></td><td>Joined non-deleted Flipnote/Creator's Room lookups.</td></tr>
<tr><td><code>GetFlipnote()</code></td><td>Compatibility wrapper returning a row or <code>False</code>.</td></tr>
<tr><td><code>GetFlipnotePPM()</code> / <code>GetFlipnoteTMB()</code></td><td>Reads whole PPM bytes or the first <code>0x6A0</code> thumbnail/metadata bytes.</td></tr>
<tr><td><code>list_flipnotes()</code></td><td>Filtered, sorted, paginated Flipnote query used by both web and DSi lists.</td></tr>
<tr><td><code>count_flipnotes()</code></td><td>Counts non-deleted Flipnotes globally or by channel/room.</td></tr>
<tr><td><code>Newest</code></td><td>Compatibility property returning <code>(creator_fsid, filename)</code> pairs for all current notes.</td></tr>
<tr><td><code>Views</code> / <code>Stars</code></td><td>Aggregate counters over non-deleted Flipnotes.</td></tr>
<tr><td><code>AddView()</code>, <code>AddDownload()</code>, <code>AddStar()</code></td><td>Atomic counter increments. Star amounts are clamped to 1–65535.</td></tr>
<tr><td><code>delete_flipnote()</code></td><td>Sets <code>deleted=1</code> for the row.</td></tr>
<tr><td><code>add_text_comment()</code></td><td>Normalises/truncates text, resolves a Creator's Room and inserts a text comment.</td></tr>
<tr><td><code>add_memo_comment()</code></td><td>Parses PPM metadata, resolves a room, inserts the row, writes <code>&lt;id&gt;.ppm</code> and updates <code>memo_filename</code>.</td></tr>
<tr><td><code>get_comment()</code> / <code>list_comments()</code> / <code>count_comments()</code></td><td>Non-deleted comment access with Creator's Room display information.</td></tr>
<tr><td><code>comment_ppm()</code></td><td>Loads bytes for a memo-type comment when the row and file are present.</td></tr>
<tr><td><code>recent_ip_logins()</code></td><td>Returns recent IP/account associations ordered by <code>last_seen</code>. The current minimal admin page does not display this helper.</td></tr>
</tbody></table>

<h3><code>reximemo_image_formats.py</code> public surface</h3>
<p><code>decode_uploaded_image()</code> accepts bytes plus a filename/input-format hint and optional raw dimensions. It normalises standard image formats through Pillow and raw Nintendo formats through the local decoders, then returns <code>DecodedImage</code>. There is no current OSE web upload route using this function; it remains a reusable format utility.</p>
<p><code>encode_image()</code> accepts a Pillow image and an output format key. It delegates to the proprietary encoders or Pillow standard writers and returns <code>EncodedImage</code>. <code>image_characteristics()</code> reports useful source properties such as size/mode/alpha. <code>ConversionError</code> is the module's input/format validation exception.</p>
</section>

<section id="admin" class="docs-section">
<h2>Admin and bans</h2>
<p>An account reaches <code>/admin</code> only when <code>is_admin</code> is 1. OSE's admin page has two jobs: maintain <code>ip_bans</code> and soft-delete Flipnotes.</p>
<p>Banning inserts or updates the exact text IP value and removes any login row for that address. The top-level router checks bans on every request, so a banned address cannot reach the browser pages, DSi resources or static content through the normal root resource.</p>
<p>Unban deletes the matching row. There are no subnet rules, expiry times, device bans, case queues, strike systems or hidden moderation states. The optional reason is limited to 200 characters and is only shown in the admin table.</p>
<div class="docs-notice"><strong>Moderation notice.</strong> IP banning and soft deletion are intentionally much simpler than RexiMemo's private moderation system. OSE leaves out device bans, behavioural/bot detection, case tooling and other production anti-abuse logic so those systems are not disclosed in a public release. Exact-IP bans are easy to understand but can affect shared networks and can be bypassed when a user's public address changes.</div>
</section>

<section id="configuration" class="docs-section">
<h2>Configuration</h2>
<table class="docs-table"><thead><tr><th>Setting</th><th>Default</th><th>Use</th></tr></thead><tbody>
<tr><td><code>REXIMEMO_PORT</code></td><td><code>8080</code></td><td>TCP listen port read by <code>server.py</code>.</td></tr>
<tr><td><code>REXIMEMO_DB</code></td><td><code>database/reximemo.sqlite3</code></td><td>Alternative SQLite file path read when <code>DatabaseBackend</code> is constructed.</td></tr>
<tr><td><code>docs:enabled</code></td><td>off</td><td>Command-line flag enabling the built-in web documentation route and navigation item.</td></tr>
<tr><td>DSi proxy</td><td>server IP, port <code>8080</code></td><td>Set in the DSi connection settings. OSE is the Hatena HTTP proxy/server; DNS/auth/NAS must be supplied separately.</td></tr>
</tbody></table>
<p>There is no separate configuration file parser in OSE. Channel 1 and the default administrator are database seed data. DSi host names are constants in <code>reximemo.py</code>/<code>hatena.py</code>.</p>
<div class="docs-notice"><strong>Configuration notice.</strong> OSE favours explicit, visible defaults over a production secrets/configuration stack. Do not place private keys, service tokens or live production credentials into the repository to compensate for missing configuration features. Keep deployment secrets outside the checkout and change the public seed administrator if the instance is reachable by others.</div>
</section>

<section id="assets" class="docs-section">
<h2>Assets and styling</h2>
<p>The web interface uses <code>web/static/site.css</code> and <code>web/static/RexiMemo_OSE_Logo.png</code>. The logo is the RexiMemo mark rendered in white with “Open Source Edition” included in the image. The main web accent is <code>#b13b29</code>. Fonts are ordinary system/browser fonts; no TTF, OTF, WOFF or WOFF2 files are part of the release.</p>
<p>The browser layout is intentionally reminiscent of the older RexiMemo site without copying the production interface one-for-one. It uses a coloured header, compact navigation, bordered dark panels, Flipnote cards and responsive grid breakpoints.</p>
<p>DSi placeholder artwork is generated locally and is not copied from production artwork. Re-run <code>python3 tools/generate_placeholders.py</code> after changing the simple icon drawings or encoder.</p>
</section>

<section id="tests" class="docs-section">
<h2>Tests</h2>
<p>The test suite uses the standard library <code>unittest</code> runner:</p>
<pre><code>python3 -m unittest discover -s tests -v</code></pre>
<p><code>test_database.py</code> creates a temporary SQLite database and checks the default administrator, IP login/logout, stable guest-room ownership and IP bans.</p>
<p><code>test_resources.py</code> can run even when Twisted is not installed by installing a small in-process Twisted resource/static-file stub. It changes into the repository root, builds the resource tree, checks expected DSi nodes, validates 2048-byte NTFT icons, confirms UGO resources begin with <code>UGAR</code>, renders the main web pages and verifies PNG thumbnail output. It also checks that Docs is hidden by default and renderable when a <code>WebRoot</code> is explicitly created with documentation enabled.</p>
<p><code>test_release_shape.py</code> scans the checkout for blocked key/certificate/font extensions, checks that named production-only components are absent, requires exactly three sample PPMs, and checks the OSE web branding and login wording.</p>
<p>These tests are smoke/shape checks, not a substitute for testing on a physical DSi. The DSi resource tests verify routing and generated binary structures inside Python; they do not emulate the full Flipnote Studio browser/network stack.</p>
<div class="docs-notice"><strong>Test-scope notice.</strong> Passing this suite does not constitute a security review. In particular it does not prove resistance to hostile traffic, credential attacks, parser abuse, proxy misconfiguration or IP-identity edge cases. The release tests concentrate on keeping OSE small, reproducible, free of private material and compatible with the retained DSi paths.</div>
</section>

<section id="changing" class="docs-section">
<h2>Changing the server</h2>
<h3>Adding a browser page</h3>
<p>Add a path branch to <code>WebRoot.render_GET()</code> or <code>render_POST()</code>. Use <code>_page()</code> for the shared shell. Escape any database/user-provided values with <code>html.escape()</code>, using <code>quote=True</code> for attribute values. Add CSS to <code>web/static/site.css</code>. If the page should be navigable globally, add it to <code>_page()</code>'s navigation construction.</p>
<div class="docs-notice"><strong>Extension notice.</strong> New authenticated, upload or moderation features should not copy assumptions from the simplified OSE identity model without considering their threat model. The repository intentionally omits production security components rather than publishing them, so an extension that needs stronger guarantees should introduce its own suitable authentication, validation, rate limiting and audit behaviour.</div>
<h3>Adding a DSi endpoint</h3>
<p>For a new top-level DSi resource, place a <code>.py</code> file under <code>hatenadir/ds/v2-xx</code> and expose a <code>PyResource</code> class. The loader mounts an instance automatically at server start. For subpaths, make the resource non-leaf and return child Resource objects from <code>getChild()</code>. Keep responses simple and compatible with the DSi browser; use existing helpers for dialogs, forwarding, UGO menus and HTML wrappers.</p>
<h3>Adding a database field</h3>
<p>Extend the <code>CREATE TABLE IF NOT EXISTS</code> schema and provide an upgrade path for existing SQLite files if the field cannot be added transparently. The current schema creation code creates missing tables/indexes but is not a general migration framework. Queries return rows as plain dictionaries through <code>_row()</code>.</p>
<h3>Adding a channel</h3>
<p>Insert a new row in <code>channels</code>. The DSi <code>ch.py</code> resource accepts any numeric channel ID present in that table. OSE's supplied home menus still post to channel 1 unless their generated URLs are changed.</p>
<h3>Changing sample data</h3>
<p>Keep SQLite records and files in <code>database/Creators</code> consistent. A Flipnote row requires the matching upper-case FSID directory and <code>&lt;filename&gt;.ppm</code>. The release-shape test currently expects exactly three PPM samples.</p>
</section>

<section id="limits" class="docs-section">
<h2>Deliberately absent systems</h2>
<p>OSE is not the production RexiMemo service. The public repository does not contain Nintendo NAS/DNS/auth gateway code, certificate/private-key material, production session/device management, FSID ownership proof, PPM signature verification, emulator/bot detection, passkeys, profile pictures, Creator's Room themes, experiments, Sudomemo migration, Discord integration, support-centre flows, policy/terms pages, notifications, production API tokens, web PPM upload, advanced moderation cases or the production moderation toolset.</p>
<div class="docs-notice"><strong>Why the simplification exists.</strong> This is a deliberate release-safety boundary. Security-sensitive production systems, secrets, trust checks and anti-abuse implementation details are excluded so publishing OSE is less likely to disclose or couple itself to RexiMemo's live infrastructure. The public replacements are intentionally smaller and easier to inspect. They exist to reduce the amount of sensitive production material exposed by an open-source release, not because a simpler login, ban or verification mechanism is inherently more secure.</div>
<p>The remaining code should be read with that boundary in mind. An OSE Creator's Room is an account-or-IP ownership record; a login is an IP-to-account database row; a ban is an exact IP row; a web Flipnote preview is frame zero; and the server accepts the old proxy-style DSi HTTP path rather than reproducing the removed network/authentication stack.</p>
<p>For public deployment work, the places most likely to need replacement or expansion are the password hashing, IP login identity, proxy/reverse-proxy IP handling, transport/authentication boundary, request-rate controls, database migrations, moderation controls, content limits/backups and operational logging. Those are outside the scope of this repository rather than hidden behind the Docs flag.</p>
</section>
</article>
</div>
'''
