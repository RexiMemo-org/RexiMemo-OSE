import html
from twisted.web import resource

from DB import Database
from hatena import NotFound, as_text, client_ip
from reximemo import current_account, dialog, dsi_url, forward, html_page, keyboard_value


class PyResource(resource.Resource):
    isLeaf = False
    def getChild(self, name, request):
        action = as_text(name)
        if action in {"account.htm", "login.kbd", "register.kbd", "logout.htm"}:
            return AccountLeaf(action)
        return NotFound


class AccountLeaf(resource.Resource):
    isLeaf = True
    def __init__(self, action):
        super().__init__(); self.action = action

    def render_GET(self, request):
        account = current_account(request)
        if self.action == "logout.htm":
            Database.logout_ip(client_ip(request))
            forward(request, dsi_url(request, "index.ugo"))
            return b"OK"
        if self.action != "account.htm":
            request.setResponseCode(405); return b""
        if account:
            room = Database.room_for_account(account["id"])
            room_link = '<p><a href="%s">Creator\'s Room</a></p>' % html.escape(dsi_url(request, f"creator/{room['id']}/profile.htm"), quote=True) if room else '<p>Your Creator\'s Room is created after your first post.</p>'
            body = '<div class="title">Account</div><p>Signed in as <strong>%s</strong>.</p>%s<p><a href="%s">Sign out</a></p>' % (html.escape(account["username"]), room_link, html.escape(dsi_url(request, "sa/logout.htm"), quote=True))
        else:
            body = '<div class="title">Account</div><p>OSE uses one simple IP login. Enter <strong>username:password</strong> in the keyboard.</p><p><a href="%s">Sign in</a></p><p><a href="%s">Register</a></p>' % (html.escape(dsi_url(request, "sa/login.kbd"), quote=True), html.escape(dsi_url(request, "sa/register.kbd"), quote=True))
        return html_page(request, "Account", body)

    def render_POST(self, request):
        if self.action not in {"login.kbd", "register.kbd"}:
            request.setResponseCode(405); return b""
        value = keyboard_value(request)
        if ":" not in value:
            return dialog(request, "Enter username:password")
        username, password = value.split(":", 1)
        if self.action == "login.kbd":
            account = Database.verify_account(username, password)
            if not account:
                return dialog(request, "Sign in failed.", 403)
            Database.login_ip(client_ip(request), account["id"])
        else:
            try:
                aid = Database.create_account(username, password)
                Database.login_ip(client_ip(request), aid)
            except ValueError as exc:
                return dialog(request, str(exc))
        forward(request, dsi_url(request, "sa/account.htm"))
        return b"OK"
