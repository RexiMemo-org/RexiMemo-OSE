from twisted.web import resource

from DB import Database
from hatena import NotFound, as_text, client_ip
from reximemo import current_account, dialog, dsi_url, flipnote_buttons, html_page, make_menu


class PyResource(resource.Resource):
    isLeaf = False
    def getChild(self, name, request):
        text = as_text(name)
        base, dot, ext = text.partition(".")
        if not dot or not base.isdigit() or ext not in {"ugo", "uls", "htm", "post"}:
            return NotFound
        channel = Database.get_channel(int(base))
        return ChannelResource(int(base), ext) if channel else NotFound

    def render(self, request):
        request.setResponseCode(403); return b""


class ChannelResource(resource.Resource):
    isLeaf = True
    def __init__(self, channel_id, ext):
        super().__init__(); self.channel_id = channel_id; self.ext = ext

    def render_GET(self, request):
        channel = Database.get_channel(self.channel_id)
        if self.ext in {"ugo", "uls"}:
            rows = Database.list_flipnotes(channel_id=self.channel_id, limit=50)
            request.setHeader(b"content-type", b"text/plain")
            return make_menu(
                layout=(2,1), title=channel["title"], subtitle_top="Channel", subtitle_bottom=channel["description"],
                left="Flipnotes", right=str(Database.count_flipnotes(channel_id=self.channel_id)),
                buttons=flipnote_buttons(request, rows), corner={"label":"Post", "url":dsi_url(request, f"ch/{self.channel_id}.post")},
            )
        if self.ext == "htm":
            return html_page(request, channel["title"], '<div class="title">%s</div><p>%s</p><p><a href="%s">Browse</a></p>' % (channel["title"], channel["description"], dsi_url(request, f"ch/{self.channel_id}.uls")))
        request.setResponseCode(405); return b""

    def render_POST(self, request):
        if self.ext != "post":
            request.setResponseCode(405); return b""
        data = request.content.read()
        account = current_account(request)
        try:
            result = Database.AddFlipnote(data, str(self.channel_id), account["id"] if account else None, client_ip(request))
        except Exception:
            result = False
        if not result:
            return dialog(request, "Unable to post this Flipnote. It may already exist or be invalid.")
        return b""
