import html
from twisted.web import resource

from DB import Database
from hatena import NotFound, as_text
from reximemo import dsi_url, flipnote_buttons, html_page, make_menu


class PyResource(resource.Resource):
    isLeaf = False
    def getChild(self, name, request):
        try:
            room_id = int(as_text(name))
        except ValueError:
            return NotFound
        return CreatorNode(room_id) if Database.get_creator_room(room_id) else NotFound


class CreatorNode(resource.Resource):
    isLeaf = False
    def __init__(self, room_id):
        super().__init__(); self.room_id = room_id
    def getChild(self, name, request):
        text = as_text(name)
        aliases = {"room.ugo":"room.uls", "movies.ugo":"movies.uls"}
        text = aliases.get(text, text)
        if text in {"profile.htm", "room.uls", "movies.uls"}:
            return CreatorLeaf(self.room_id, text)
        return NotFound


class CreatorLeaf(resource.Resource):
    isLeaf = True
    def __init__(self, room_id, action):
        super().__init__(); self.room_id = room_id; self.action = action

    def render_GET(self, request):
        room = Database.get_creator_room(self.room_id)
        if not room:
            return NotFound.render(request)
        notes = Database.list_creator_flipnotes(self.room_id, limit=50)
        if self.action in {"room.uls", "movies.uls"}:
            request.setHeader(b"content-type", b"text/plain")
            return make_menu(
                layout=(2,1), title=room["display_name"], subtitle_top="Creator's Room",
                left="Flipnotes", right=str(len(notes)), buttons=flipnote_buttons(request, notes),
                corner={"label":"Post", "url":dsi_url(request, "ch/1.post")},
            )
        profile = (
            '<div class="title" align="center">%s</div>'
            '<div class="notice2" align="center">Creator\'s Room</div>'
            '<table width="226" class="detail">'
            '<tr><th>Flipnotes</th><td>%d</td></tr>'
            '<tr><th>Identity</th><td>%s</td></tr>'
            '</table><p><a href="%s">View Flipnotes</a></p>'
        ) % (
            html.escape(room["display_name"]), len(notes),
            "Account" if room.get("account_id") else "Guest/IP",
            html.escape(dsi_url(request, f"creator/{self.room_id}/movies.uls"), quote=True),
        )
        return html_page(request, room["display_name"], profile)
