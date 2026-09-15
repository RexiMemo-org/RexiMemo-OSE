from twisted.web import resource
from reximemo import make_menu

class PyResource(resource.Resource):
    isLeaf = True
    def render_GET(self, request):
        request.setHeader(b"content-type", b"text/plain")
        return make_menu(layout=(4,), title="Inbox", subtitle_bottom="Notifications are not included in OSE.", buttons=[])
