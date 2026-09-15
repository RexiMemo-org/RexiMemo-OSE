from twisted.web import resource

from DB import Database
from hatena import NotFound, as_text, request_args
from reximemo import comment_npf


class PyResource(resource.Resource):
    isLeaf = False
    def getChild(self, name, request):
        text = as_text(name)
        base, dot, ext = text.partition(".")
        if not dot or not base.isdigit() or ext not in {"npf", "ppm"}:
            return NotFound
        return CommentFile(int(base), ext) if Database.get_comment(int(base)) else NotFound


class CommentFile(resource.Resource):
    isLeaf = True
    def __init__(self, cid, ext):
        super().__init__(); self.cid = cid; self.ext = ext
    def render_GET(self, request):
        if self.ext == "ppm":
            data = Database.comment_ppm(self.cid)
            if data is None:
                return NotFound.render(request)
            request.setHeader(b"content-type", b"application/octet-stream")
            return data
        args = request_args(request)
        try: w = max(1, min(256, int(args.get("w", ["128"])[0])))
        except ValueError: w = 128
        try: h = max(1, min(192, int(args.get("h", ["64"])[0])))
        except ValueError: h = 64
        data = comment_npf(self.cid, w, h)
        if data is None:
            return NotFound.render(request)
        request.setHeader(b"content-type", b"application/octet-stream")
        return data
