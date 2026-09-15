from __future__ import annotations

import html
from urllib.parse import parse_qs

from twisted.web import resource

from DB import Database
from hatena import client_ip, request_args
from reximemo import ppm_thumbnail_png


def _fields(request):
    try:
        raw = request.content.read().decode("utf-8", "replace")
    except Exception:
        raw = ""
    return {k: v[-1] if v else "" for k, v in parse_qs(raw, keep_blank_values=True).items()}


def _redirect(request, path):
    request.setResponseCode(303)
    request.setHeader(b"Location", str(path).encode("utf-8"))
    return b""


def _fmt_time(ts):
    import datetime
    try:
        return datetime.datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


class WebRoot(resource.Resource):
    isLeaf = True

    def __init__(self, docs_enabled=False):
        super().__init__()
        self.docs_enabled = bool(docs_enabled)

    def _account(self, request):
        return Database.account_for_ip(client_ip(request))

    def _page(self, request, title, body, *, account=None, active=""):
        account = account if account is not None else self._account(request)
        browse_class = " active" if active == "browse" else ""
        home_class = " active" if active == "home" else ""
        account_class = " active" if active == "account" else ""
        admin_class = " active" if active == "admin" else ""
        about_class = " active" if active == "about" else ""
        docs_class = " active" if active == "docs" else ""
        nav_html = (
            f'<a class="nav-link{home_class}" href="/">Home</a>'
            f'<a class="nav-link{browse_class}" href="/browse">Browse</a>'
            f'<a class="nav-link{about_class}" href="/about">About</a>'
        )
        if self.docs_enabled:
            nav_html += f'<a class="nav-link{docs_class}" href="/docs">Docs</a>'
        if account:
            actions = f'<a class="nav-action ghost{account_class}" href="/account">{html.escape(account["username"])}</a>'
            if int(account.get("is_admin") or 0):
                actions += f'<a class="nav-action{admin_class}" href="/admin">Admin</a>'
        else:
            actions = '<a class="nav-action ghost" href="/login">Sign in</a><a class="nav-action" href="/register">Create account</a>'

        full_title = "RexiMemo OSE" if title == "Home" else f"{html.escape(title)} · RexiMemo OSE"
        docs_footer = '<a href="/docs">Docs</a>' if self.docs_enabled else ""
        page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{full_title}</title><meta name="theme-color" content="#b13b29"><link rel="stylesheet" href="/static/site.css"></head>
<body><header class="site-header"><div class="header-inner">
<a class="brand" href="/" aria-label="RexiMemo Open Source Edition"><img src="/static/RexiMemo_OSE_Logo.png" alt="RexiMemo! Open Source Edition"></a>
<nav class="main-nav">{nav_html}</nav><div class="header-actions">{actions}</div>
</div></header><main class="page-shell">{body}</main>
<footer class="site-footer"><div><strong>RexiMemo: Open Source Edition</strong><span>AGPL-3.0</span></div><div><a href="/browse">Browse Flipnotes</a><a href="/about">About</a>{docs_footer}</div></footer></body></html>"""
        request.setHeader(b"content-type", b"text/html; charset=utf-8")
        return page.encode("utf-8")

    def _flipnote_card(self, fn):
        return (
            '<article class="flipnote-card">'
            '<a class="flipnote-thumb" href="/watch/%(public)s"><img loading="lazy" src="/thumb/%(public)s.png" alt=""></a>'
            '<div class="flipnote-card-body"><a class="flipnote-title" href="/watch/%(public)s">%(title)s</a>'
            '<a class="flipnote-creator" href="/creator/%(creator)s">%(creator_name)s</a>'
            '<div class="flipnote-meta"><span>%(stars)s ★</span><span>%(views)s views</span></div></div>'
            '</article>'
        ) % {
            "public": html.escape(fn["public_id"], quote=True),
            "creator": html.escape(fn["creator_public_id"], quote=True),
            "creator_name": html.escape(fn["creator_name"]),
            "title": html.escape(fn.get("title") or "Untitled Flipnote"),
            "stars": int(fn.get("stars") or 0),
            "views": int(fn.get("views") or 0),
        }

    def render_GET(self, request):
        path = request.path.decode("utf-8", "replace")
        account = self._account(request)
        if path == "/":
            rows = Database.list_flipnotes(limit=12)
            body = (
                '<section class="home-intro-card"><div class="home-intro-main">'
                '<span class="home-intro-eyebrow">Open Source Edition</span>'
                '<strong>RexiMemo!</strong><p>A small Flipnote Hatena-compatible server.</p></div>'
                '<div class="home-intro-actions"><a class="button primary" href="/browse">Browse Flipnotes</a></div></section>'
                '<section class="section first-section"><div class="section-head"><h1>Recent Flipnotes</h1><a href="/browse">View all</a></div>'
                '<div class="flipnote-grid">' + "".join(self._flipnote_card(r) for r in rows) + "</div></section>"
            )
            if not rows:
                body += '<p class="empty-state">No Flipnotes have been posted yet.</p>'
            return self._page(request, "Home", body, account=account, active="home")

        if path == "/about":
            body = (
                '<header class="page-head"><div><h1>About</h1><p>Open-source projects and community work used by RexiMemo OSE.</p></div></header>'
                '<section class="panel about-panel"><div class="panel-title">Open-source credits</div><div class="about-body">'
                '<p>RexiMemo OSE builds on earlier Flipnote preservation and replacement-server work. The projects below are included directly or used by the server.</p>'
                '<div class="credit-list">'
                '<div class="credit-item"><strong><a href="https://github.com/pbsds/hatena-server">pbsds / hatena-server</a></strong><small>AGPL-3.0</small><p>The original open-source Flipnote Hatena replacement server and the main foundation for the older public server code.</p></div>'
                '<div class="credit-item"><strong><a href="https://github.com/pbsds/Hatenatools">Hatenatools</a></strong><small>AGPL-3.0 · pbsds and contributors</small><p>Utilities for PPM/TMB, UGO, NTFT and related Nintendo DSi and Flipnote formats. The bundled copy has been ported to Python 3.</p></div>'
                '<div class="credit-item"><strong><a href="https://flipnote.js.org/">flipnote.js</a></strong><small>MIT · James Daniel</small><p>Browser-side PPM decoding, animation rendering and audio playback on Flipnote pages.</p></div>'
                '<div class="credit-item"><strong><a href="https://www.python.org/">Python</a></strong><small>PSF License</small><p>The language and runtime used by RexiMemo OSE.</p></div>'
                '<div class="credit-item"><strong><a href="https://twisted.org/">Twisted</a></strong><small>MIT</small><p>The networking and HTTP framework used by the server.</p></div>'
                '<div class="credit-item"><strong><a href="https://numpy.org/">NumPy</a></strong><small>BSD-3-Clause</small><p>Used by the legacy Flipnote media and format tools.</p></div>'
                '<div class="credit-item"><strong><a href="https://python-pillow.github.io/">Pillow</a></strong><small>MIT-CMU</small><p>Used for image decoding and thumbnail generation.</p></div>'
                '</div></div></section>'
                '<section class="panel about-panel section"><div class="panel-title">Acknowledgements</div><div class="about-body">'
                "<p>Credit also goes to the Flipnote preservation and reverse-engineering community, including the people who documented Flipnote formats, DSi image formats, UGO menus, audio codecs and the original service's network behaviour.</p>"
                '<p>The Hatenatools sources included in this repository also credit Steven, Remark, JSAfive, Austin Burk, Midmad and WDLmaster for format research and sample files.</p>'
                '</div></section>'
                '<p class="about-note">RexiMemo is an independent project and is not affiliated with Nintendo or Hatena. Third-party software and names remain the property of their respective owners.</p>'
            )
            return self._page(request, "About", body, account=account, active="about")

        if path == "/docs" and self.docs_enabled:
            from docs_page import render_docs
            return self._page(request, "Documentation", render_docs(), account=account, active="docs")

        if path == "/browse":
            sort = request_args(request).get("sort", ["new"])[0]
            if sort not in {"new", "popular", "top"}:
                sort = "new"
            rows = Database.list_flipnotes(sort=sort, limit=100)
            body = (
                '<header class="page-head split"><div><h1>Browse</h1><p>Flipnotes posted to this server.</p></div>'
                '<div class="tabs"><a href="/browse?sort=new">Newest</a><a href="/browse?sort=popular">Popular</a><a href="/browse?sort=top">Stars</a></div></header>'
                '<div class="flipnote-grid">' + "".join(self._flipnote_card(r) for r in rows) + "</div>"
            )
            if not rows:
                body += '<p class="empty-state">No Flipnotes found.</p>'
            return self._page(request, "Browse", body, account=account, active="browse")

        if path.startswith("/thumb/") and path.endswith(".png"):
            public_id = path[len("/thumb/"):-4]
            fn = Database.get_flipnote_by_public_id(public_id)
            if not fn:
                request.setResponseCode(404); return b""
            try:
                data = ppm_thumbnail_png(Database.GetFlipnotePPM(fn["creator_fsid"], fn["filename"]), (320, 240))
            except Exception:
                request.setResponseCode(500); return b""
            request.setHeader(b"content-type", b"image/png")
            request.setHeader(b"Cache-Control", b"public, max-age=3600")
            return data

        if path.startswith("/comment-thumb/") and path.endswith(".png"):
            raw_id = path[len("/comment-thumb/"):-4]
            try:
                comment_id = int(raw_id)
            except ValueError:
                request.setResponseCode(404); return b""
            raw = Database.comment_ppm(comment_id)
            if raw is None:
                request.setResponseCode(404); return b""
            try:
                data = ppm_thumbnail_png(raw, (256, 192))
            except Exception:
                request.setResponseCode(500); return b""
            request.setHeader(b"content-type", b"image/png")
            request.setHeader(b"Cache-Control", b"public, max-age=3600")
            return data

        if path.startswith("/media/") and path.endswith(".ppm"):
            public_id = path[len("/media/"):-4]
            fn = Database.get_flipnote_by_public_id(public_id)
            if not fn:
                request.setResponseCode(404); return b""
            request.setHeader(b"content-type", b"application/octet-stream")
            request.setHeader(b"content-disposition", b"inline")
            request.setHeader(b"Cache-Control", b"public, max-age=3600")
            return Database.GetFlipnotePPM(fn["creator_fsid"], fn["filename"])

        if path.startswith("/flipnote/") and path.endswith(".ppm"):
            public_id = path[len("/flipnote/"):-4]
            fn = Database.get_flipnote_by_public_id(public_id)
            if not fn:
                request.setResponseCode(404); return b""
            Database.AddDownload(fn["creator_fsid"], fn["filename"])
            request.setHeader(b"content-type", b"application/octet-stream")
            request.setHeader(b"content-disposition", (f'attachment; filename="{fn["filename"]}.ppm"').encode("ascii", "ignore"))
            return Database.GetFlipnotePPM(fn["creator_fsid"], fn["filename"])

        if path.startswith("/watch/"):
            public_id = path[len("/watch/"):].strip("/")
            fn = Database.get_flipnote_by_public_id(public_id)
            if not fn:
                request.setResponseCode(404)
                return self._page(request, "Not found", '<header class="page-head"><h1>Flipnote not found</h1></header>', account=account)
            Database.AddView(fn["creator_fsid"], fn["filename"])
            fn = Database.get_flipnote_by_public_id(public_id)
            comments = Database.list_comments(fn["id"], limit=100)
            channel = Database.get_channel(fn["channel_id"]) if fn.get("channel_id") else None
            room = Database.get_creator_room(fn["creator_room_id"])
            related = [r for r in Database.list_creator_flipnotes(fn["creator_room_id"], limit=8) if int(r["id"]) != int(fn["id"])][:4]
            try:
                ppm_size = Database.FlipnotePath(fn["creator_fsid"], fn["filename"]).stat().st_size
                size_text = "%.1f KiB" % (ppm_size / 1024.0)
            except OSError:
                size_text = "Unknown"
            rendered_comments = []
            for c in comments:
                if c["type"] == "memo":
                    content = (
                        '<a class="memo-comment-preview" href="/comment-thumb/%d.png">'
                        '<img loading="lazy" src="/comment-thumb/%d.png" alt="Mini Flipnote comment first frame">'
                        '<span>Mini Flipnote comment</span></a>' % (int(c["id"]), int(c["id"]))
                    )
                else:
                    content = '<div class="comment-text">%s</div>' % html.escape(c.get("text_content") or "")
                rendered_comments.append(
                    '<div class="comment"><div class="comment-author"><a href="/creator/%s">%s</a><small>%s</small></div><div class="comment-content">%s</div></div>' % (
                        html.escape(c["creator_public_id"], quote=True), html.escape(c["creator_name"]), _fmt_time(c["posted_at"]), content
                    )
                )
            comment_form = (
                '<form method="post" action="/watch/%s/comment" class="comment-form">'
                '<input name="text" maxlength="500" placeholder="Write a comment"><button class="button primary">Post comment</button></form>'
            ) % html.escape(public_id, quote=True)
            related_html = "".join(self._flipnote_card(r) for r in related)
            body = (
                '<header class="watch-head"><div><div class="watch-kicker">Flipnote</div><h1>%(title)s</h1>'
                '<p>by <a href="/creator/%(creator)s">%(creator_name)s</a> <span>·</span> %(posted)s</p></div>'
                '<a class="button subtle" href="/creator/%(creator)s">Creator\'s Room</a></header>'
                '<div class="watch-layout watch-layout-rich"><section class="player-card watch-preview">'
                '<div class="preview-bar"><span>Flipnote player</span><span>PPM · flipnote.js</span></div>'
                '<div class="preview-stage flipnote-stage" data-flipnote-player data-source="/media/%(public)s.ppm">'
                '<div class="flipnote-player-canvas" aria-label="Flipnote playback canvas"></div>'
                '<img class="flipnote-player-fallback" data-fallback-label="First-frame preview" src="/thumb/%(public)s.png" alt="First frame of %(title_attr)s">'
                '<button class="flipnote-big-play" type="button" data-action="big-play" aria-label="Play Flipnote" hidden>▶</button>'
                '<div class="flipnote-player-status" data-display="status" role="status">Loading Flipnote…</div></div>'
                '<div class="flipnote-controls" aria-label="Flipnote playback controls">'
                '<button class="flipnote-control-button play-control" type="button" data-action="play" disabled>Play</button>'
                '<input class="flipnote-progress" data-control="progress" type="range" min="0" max="1000" value="0" step="1" aria-label="Playback position" disabled>'
                '<span class="flipnote-time" data-display="time">0:00 / 0:00</span>'
                '<button class="flipnote-control-button" type="button" data-action="mute" disabled>Sound</button>'
                '<button class="flipnote-control-button" type="button" data-action="loop" aria-pressed="false" disabled>Loop</button></div>'
                '<div class="preview-footer"><span>Played in-browser with flipnote.js.</span><a href="/flipnote/%(public)s.ppm">Download original</a></div>'
                '</section><aside class="detail-panel watch-details"><div class="creator-summary"><span class="creator-label">Creator</span>'
                '<a class="creator-name" href="/creator/%(creator)s">%(creator_name)s</a><span>%(identity)s</span></div>'
                '<div class="watch-stat-grid"><div><strong>%(stars)s</strong><span>Stars</span></div><div><strong>%(views)s</strong><span>Views</span></div>'
                '<div><strong>%(downloads)s</strong><span>Downloads</span></div><div><strong>%(comment_count)s</strong><span>Comments</span></div></div>'
                '<div class="watch-info"><div><span>Posted</span><strong>%(posted)s</strong></div><div><span>Channel</span><strong>%(channel)s</strong></div>'
                '<div><span>FSID</span><code>%(fsid)s</code></div><div><span>Filename</span><code>%(filename)s</code></div>'
                '<div><span>File size</span><strong>%(size)s</strong></div><div><span>Public ID</span><code>%(public)s</code></div></div>'
                '<a class="button primary wide" href="/flipnote/%(public)s.ppm">Download PPM</a></aside></div>'
                '<section class="comments-panel section"><div class="panel-title comments-title"><span>Comments</span><span>%(comment_count)s</span></div>'
                '<div class="comments-body">%(form)s<div class="comments">%(comments)s</div></div></section>'
                '%(related_section)s'
                '<script src="https://cdn.jsdelivr.net/npm/flipnote.js@6.3.1/dist/flipnote.min.js"></script>'
                '<script src="/static/flipnote-player.js"></script>'
            ) % {
                "public": html.escape(fn["public_id"], quote=True),
                "title": html.escape(fn.get("title") or "Untitled Flipnote"),
                "title_attr": html.escape(fn.get("title") or "Untitled Flipnote", quote=True),
                "creator": html.escape(fn["creator_public_id"], quote=True),
                "creator_name": html.escape(fn["creator_name"]),
                "identity": "Account Creator's Room" if room and room.get("account_id") else "Guest/IP Creator's Room",
                "stars": int(fn.get("stars") or 0),
                "views": int(fn.get("views") or 0),
                "downloads": int(fn.get("downloads") or 0),
                "comment_count": len(comments),
                "posted": _fmt_time(fn.get("posted_at")),
                "channel": html.escape((channel or {}).get("title") or "General"),
                "fsid": html.escape(fn.get("creator_fsid") or ""),
                "filename": html.escape(fn.get("filename") or ""),
                "size": html.escape(size_text),
                "form": comment_form,
                "comments": "".join(rendered_comments) or '<p class="empty-state small">No comments yet.</p>',
                "related_section": (
                    '<section class="section"><div class="section-head"><h2>More from %s</h2><a href="/creator/%s">Open Creator\'s Room</a></div><div class="flipnote-grid related-grid">%s</div></section>'
                    % (html.escape(fn["creator_name"]), html.escape(fn["creator_public_id"], quote=True), related_html)
                ) if related_html else "",
            }
            return self._page(request, fn.get("title") or "Flipnote", body, account=account)

        if path.startswith("/creator/"):
            public_id = path[len("/creator/"):].strip("/")
            room = Database.get_creator_room_by_public_id(public_id)
            if not room:
                request.setResponseCode(404)
                return self._page(request, "Not found", '<header class="page-head"><h1>Creator not found</h1></header>', account=account)
            notes = Database.list_creator_flipnotes(room["id"], limit=100)
            owner = "Account" if room.get("account_id") else "Guest/IP creator"
            body = (
                '<header class="page-head creator-head"><div><h1>%s</h1><p>%s · Room created when this creator first posted a Flipnote.</p></div></header>'
                '<section class="section first-section"><div class="section-head"><h2>Posted Flipnotes</h2><span>%d</span></div>'
                '<div class="flipnote-grid">%s</div></section>'
            ) % (html.escape(room["display_name"]), owner, len(notes), "".join(self._flipnote_card(r) for r in notes))
            return self._page(request, room["display_name"], body, account=account)

        if path == "/login":
            body = (
                '<div class="auth-wrap"><section class="auth-card"><div class="panel-title">Sign in</div><div class="auth-body">'
                '<p class="notice">OSE login state is tied to your IP address.</p>'
                '<form method="post" class="stacked-form"><label>Username<input name="username" autocomplete="username"></label>'
                '<label>Password<input type="password" name="password" autocomplete="current-password"></label>'
                '<button class="button primary wide">Sign in</button></form><p class="auth-link"><a href="/register">Create an account</a></p></div></section></div>'
            )
            return self._page(request, "Sign in", body, account=account)

        if path == "/register":
            body = (
                '<div class="auth-wrap"><section class="auth-card"><div class="panel-title">Create account</div><div class="auth-body">'
                '<form method="post" class="stacked-form"><label>Username<input name="username" maxlength="24"></label>'
                '<label>Password<input type="password" name="password"></label><button class="button primary wide">Create account</button></form>'
                '<p class="auth-link"><a href="/login">Already have an account?</a></p></div></section></div>'
            )
            return self._page(request, "Create account", body, account=account)

        if path == "/logout":
            Database.logout_ip(client_ip(request))
            return _redirect(request, "/")

        if path == "/account":
            if not account:
                return _redirect(request, "/login")
            room = Database.room_for_account(account["id"])
            room_link = '<a class="button" href="/creator/%s">Open Creator\'s Room</a>' % html.escape(room["public_id"], quote=True) if room else "Creator's Room will be created after your first Flipnote post."
            body = (
                '<header class="page-head"><div><h1>%s</h1><p>Account</p></div></header>'
                '<section class="panel account-panel"><div class="panel-title">Account details</div><div class="detail-body"><p>%s</p>'
                '<dl class="account-list"><div><dt>Login IP</dt><dd><code>%s</code></dd></div></dl><a class="button subtle" href="/logout">Sign out this IP</a></div></section>'
            ) % (html.escape(account["username"]), room_link, html.escape(client_ip(request)))
            return self._page(request, "Account", body, account=account, active="account")

        if path == "/admin":
            if not account or not int(account.get("is_admin") or 0):
                request.setResponseCode(403)
                return self._page(request, "Admin", '<header class="page-head"><h1>Admin access required</h1></header>', account=account)
            bans = Database.list_bans()
            notes = Database.list_flipnotes(limit=100)
            ban_rows = "".join('<tr><td><code>%s</code></td><td>%s</td><td><form method="post" action="/admin/unban"><input type="hidden" name="ip" value="%s"><button class="button small">Unban</button></form></td></tr>' % (html.escape(b["ip"]), html.escape(b.get("reason") or ""), html.escape(b["ip"], quote=True)) for b in bans)
            note_rows = "".join('<tr><td>%s</td><td>%s</td><td><form method="post" action="/admin/delete"><input type="hidden" name="id" value="%d"><button class="button small danger">Delete</button></form></td></tr>' % (html.escape(n["title"]), html.escape(n["creator_name"]), int(n["id"])) for n in notes)
            body = (
                '<header class="page-head"><div><h1>Admin</h1><p>IP bans and Flipnote deletion.</p></div></header>'
                '<section class="panel"><div class="panel-title">Ban IP</div><form method="post" action="/admin/ban" class="admin-ban-form"><input name="ip" placeholder="IP address"><input name="reason" placeholder="Reason"><button class="button primary">Ban</button></form></section>'
                '<section class="section"><div class="section-head"><h2>Blocked IPs</h2></div><div class="table-wrap"><table><tr><th>IP</th><th>Reason</th><th></th></tr>%s</table></div></section>'
                '<section class="section"><div class="section-head"><h2>Flipnotes</h2></div><div class="table-wrap"><table><tr><th>Title</th><th>Creator</th><th></th></tr>%s</table></div></section>'
            ) % (ban_rows, note_rows)
            return self._page(request, "Admin", body, account=account, active="admin")

        request.setResponseCode(404)
        return self._page(request, "Not found", '<header class="page-head"><h1>Not found</h1></header>', account=account)

    def render_POST(self, request):
        path = request.path.decode("utf-8", "replace")
        fields = _fields(request)
        ip = client_ip(request)
        account = self._account(request)

        if path == "/login":
            found = Database.verify_account(fields.get("username", ""), fields.get("password", ""))
            if not found:
                request.setResponseCode(403)
                return self._page(request, "Sign in", '<header class="page-head"><h1>Sign in failed</h1></header><p><a href="/login">Try again</a></p>', account=None)
            Database.login_ip(ip, found["id"])
            return _redirect(request, "/account")

        if path == "/register":
            try:
                aid = Database.create_account(fields.get("username", ""), fields.get("password", ""))
                Database.login_ip(ip, aid)
            except ValueError as exc:
                request.setResponseCode(400)
                return self._page(request, "Create account", '<header class="page-head"><h1>Could not create account</h1></header><p>%s</p>' % html.escape(str(exc)), account=None)
            return _redirect(request, "/account")

        if path.startswith("/watch/") and path.endswith("/comment"):
            public_id = path[len("/watch/"):-len("/comment")].strip("/")
            fn = Database.get_flipnote_by_public_id(public_id)
            if not fn:
                request.setResponseCode(404); return b""
            try:
                Database.add_text_comment(fn["id"], fields.get("text", ""), ip_address=ip, account_id=(account["id"] if account else None))
            except ValueError:
                pass
            return _redirect(request, "/watch/" + public_id)

        if path.startswith("/admin/"):
            if not account or not int(account.get("is_admin") or 0):
                request.setResponseCode(403); return b""
            if path == "/admin/ban":
                try:
                    Database.ban_ip(fields.get("ip", ""), fields.get("reason", ""))
                except ValueError:
                    pass
            elif path == "/admin/unban":
                Database.unban_ip(fields.get("ip", ""))
            elif path == "/admin/delete":
                try:
                    Database.delete_flipnote(int(fields.get("id", "0")))
                except ValueError:
                    pass
            return _redirect(request, "/admin")

        request.setResponseCode(404)
        return b""
