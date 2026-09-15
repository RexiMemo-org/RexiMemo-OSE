from __future__ import annotations

import html

from twisted.web import resource

from DB import Database
from Hatenatools import TMB
from hatena import NotFound, as_text, client_ip, request_headers
from reximemo import current_account, dialog, dsi_url, forward, html_page, keyboard_value


class PyResource(resource.Resource):
    isLeaf = False
    def getChild(self, name, request):
        fsid = as_text(name).upper()
        return CreatorNode(fsid) if Database.CreatorExists(fsid) else NotFound

    def render(self, request):
        request.setResponseCode(403); return b""


class CreatorNode(resource.Resource):
    isLeaf = False
    def __init__(self, fsid):
        super().__init__(); self.fsid = fsid

    def getChild(self, name, request):
        text = as_text(name)
        if "." in text:
            base, ext = text.rsplit(".", 1)
            if ext in {"ppm", "tmb", "info", "htm", "star", "dl", "reply"} and Database.FlipnoteExists(self.fsid, base):
                return FlipnoteFile(self.fsid, base, ext)
        if Database.FlipnoteExists(self.fsid, text):
            return FlipnoteActionNode(self.fsid, text)
        return NotFound


class FlipnoteActionNode(resource.Resource):
    isLeaf = False
    def __init__(self, fsid, filename):
        super().__init__(); self.fsid = fsid; self.filename = filename
    def getChild(self, name, request):
        if as_text(name) == "keyboard.kbd":
            return TextComment(self.fsid, self.filename)
        return NotFound


class TextComment(resource.Resource):
    isLeaf = True
    def __init__(self, fsid, filename):
        super().__init__(); self.fsid = fsid; self.filename = filename
    def render_POST(self, request):
        fn = Database.get_flipnote(self.fsid, self.filename)
        if not fn:
            return NotFound.render(request)
        account = current_account(request)
        try:
            Database.add_text_comment(
                fn["id"], keyboard_value(request), ip_address=client_ip(request),
                account_id=(account["id"] if account else None),
            )
        except ValueError as exc:
            return dialog(request, str(exc))
        forward(request, dsi_url(request, f"movie/{self.fsid}/{self.filename}.htm"))
        return b"OK"
    def render_GET(self, request):
        request.setResponseCode(405); return b""


class FlipnoteFile(resource.Resource):
    isLeaf = True
    def __init__(self, fsid, filename, ext):
        super().__init__(); self.fsid = fsid; self.filename = filename; self.ext = ext

    def render_GET(self, request):
        fn = Database.get_flipnote(self.fsid, self.filename)
        if not fn:
            return NotFound.render(request)
        if self.ext == "ppm":
            Database.AddView(self.fsid, self.filename)
            request.setHeader(b"content-type", b"application/octet-stream")
            return Database.GetFlipnotePPM(self.fsid, self.filename)
        if self.ext == "tmb":
            request.setHeader(b"content-type", b"application/octet-stream")
            return Database.GetFlipnoteTMB(self.fsid, self.filename)
        if self.ext == "info":
            request.setHeader(b"content-type", b"text/plain")
            return b"0\n0\n"
        if self.ext == "dl":
            Database.AddDownload(self.fsid, self.filename)
            return b"OK"
        if self.ext == "star":
            headers = request_headers(request)
            try:
                amount = int(headers.get("x-hatena-star-count", "1"))
            except ValueError:
                amount = 1
            Database.AddStar(self.fsid, self.filename, amount)
            return b"Success"
        if self.ext == "htm":
            return details_page(request, fn)
        request.setResponseCode(405); return b""

    def render_POST(self, request):
        fn = Database.get_flipnote(self.fsid, self.filename)
        if not fn:
            return NotFound.render(request)
        if self.ext == "reply":
            data = request.content.read()
            tmb = TMB().Read(data)
            if not tmb:
                return dialog(request, "That mini Flipnote is invalid.")
            if int(getattr(tmb, "FrameCount", 1)) != 1:
                return dialog(request, "Mini Flipnote comments must contain one frame.")
            account = current_account(request)
            try:
                Database.add_memo_comment(
                    fn["id"], data, ip_address=client_ip(request),
                    account_id=(account["id"] if account else None),
                )
            except ValueError as exc:
                return dialog(request, str(exc))
            forward(request, dsi_url(request, f"movie/{self.fsid}/{self.filename}.htm"))
            return b"OK"
        request.setResponseCode(405); return b""


def details_page(request, fn):
    try:
        tmb = TMB().Read(Database.GetFlipnoteTMB(fn["creator_fsid"], fn["filename"]))
    except Exception:
        tmb = None
    creator_name = fn.get("creator_name") or (getattr(tmb, "Username", "") if tmb else "Creator")
    creator_url = dsi_url(request, f"creator/{fn['creator_room_id']}/profile.htm")
    ppm_url = dsi_url(request, f"movie/{fn['creator_fsid']}/{fn['filename']}.ppm")
    star_url = dsi_url(request, f"movie/{fn['creator_fsid']}/{fn['filename']}.star")
    reply_url = dsi_url(request, f"movie/{fn['creator_fsid']}/{fn['filename']}.reply")
    text_url = dsi_url(request, f"movie/{fn['creator_fsid']}/{fn['filename']}/keyboard.kbd")
    extra = (
        '<meta name="upperlink" content="%(ppm)s">'
        '<meta name="savebutton" content="%(ppm)s">'
        '<meta name="playcontrolbutton" content="">'
        '<meta name="starbutton" content="%(star)s">'
        '<meta name="commentbutton" content="%(reply)s">'
    ) % {
        "ppm": html.escape(ppm_url, quote=True),
        "star": html.escape(star_url, quote=True),
        "reply": html.escape(reply_url, quote=True),
    }
    comments = Database.list_comments(fn["id"], limit=30)
    comment_html = []
    for c in comments:
        if c["type"] == "memo":
            npf = dsi_url(request, f"comment/{c['id']}.npf?w=128&h=64")
            ppm = dsi_url(request, f"comment/{c['id']}.ppm")
            content = '<a href="%s"><img src="%s" width="128" height="64"></a>' % (html.escape(ppm, quote=True), html.escape(npf, quote=True))
        else:
            content = html.escape(c.get("text_content") or "")
        comment_html.append(
            '<div class="comment"><strong>%s</strong><br>%s</div><div class="hr"></div>' % (
                html.escape(c.get("creator_name") or "Guest"), content,
            )
        )
    body = (
        '<div class="title">%(title)s</div>'
        '<table width="226" class="detail">'
        '<tr><th>Creator</th><td><a href="%(creator_url)s">%(creator)s</a></td></tr>'
        '<tr><th>Stars</th><td>%(stars)d</td></tr>'
        '<tr><th>Views</th><td>%(views)d</td></tr>'
        '</table>'
        '<p><a href="%(ppm)s">Play Flipnote</a></p>'
        '<p><a href="%(text)s">Text Comment</a></p>'
        '<div class="hr"></div><div class="subtitle">Comments</div>%(comments)s'
    ) % {
        "title": html.escape(fn.get("title") or "Untitled Flipnote"),
        "creator_url": html.escape(creator_url, quote=True),
        "creator": html.escape(creator_name),
        "stars": int(fn.get("stars") or 0),
        "views": int(fn.get("views") or 0),
        "ppm": html.escape(ppm_url, quote=True),
        "text": html.escape(text_url, quote=True),
        "comments": "".join(comment_html) or '<div class="notice">No comments yet.</div>',
    }
    return html_page(request, fn.get("title") or "Flipnote", body, extra)
