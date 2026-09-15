from twisted.web import resource

from DB import Database
from reximemo import current_account, dsi_url, flipnote_buttons, make_menu, placeholder_icon


class PyResource(resource.Resource):
    isLeaf = True
    def render_GET(self, request):
        rows = Database.list_flipnotes(limit=8)
        account = current_account(request)
        buttons = [
            {"label": "Browse Flipnotes", "url": dsi_url(request, "allflipnotes.uls"), "icon_ntft": placeholder_icon("browse"), "embed_name": "browse.ntft"},
            {"label": "Account", "url": dsi_url(request, "sa/account.htm"), "icon_ntft": placeholder_icon("account"), "embed_name": "account.ntft"},
        ]
        room = Database.room_for_account(account["id"]) if account else Database.room_for_ip(__import__('hatena').client_ip(request))
        if room:
            buttons.append({"label": "Creator's Room", "url": dsi_url(request, f"creator/{room['id']}/profile.htm"), "icon_ntft": placeholder_icon("room"), "embed_name": "room.ntft"})
        buttons.extend(flipnote_buttons(request, rows))
        request.setHeader(b"content-type", b"text/plain")
        return make_menu(
            layout=(2, 1),
            title="RexiMemo OSE",
            subtitle_top="Open Source Edition",
            subtitle_bottom="Proxy build",
            left="Recent",
            right=str(Database.count_flipnotes()),
            buttons=buttons,
            corner={"label": "Post", "url": dsi_url(request, "ch/1.post")},
        )
