from twisted.web import resource
from DB import Database
from reximemo import dsi_url, flipnote_buttons, make_menu, pagination_buttons, query_int


class PyResource(resource.Resource):
    isLeaf = True
    def render_GET(self, request):
        page = query_int(request, "page", 1)
        total = Database.count_flipnotes()
        rows = Database.list_flipnotes(page=page, per_page=50)
        pager = pagination_buttons(request, "allflipnotes.uls", page, total)
        prev = [b for b in pager if b["label"].startswith("Previous")]
        nxt = [b for b in pager if b["label"].startswith("Next")]
        request.setHeader(b"content-type", b"text/plain")
        return make_menu(
            layout=(2, 1), title="Browse", subtitle_top="All Flipnotes",
            left="Flipnotes", right=str(total), buttons=prev + flipnote_buttons(request, rows) + nxt,
            corner={"label": "Post", "url": dsi_url(request, "ch/1.post")},
        )
