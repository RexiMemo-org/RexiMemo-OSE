from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import sys
from urllib.parse import urlencode

from twisted.web import resource, static

ServerLog = None
Silent = False


def as_text(value):
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else str(value)


def request_path(request):
    return as_text(request.path)


def request_headers(request):
    return {as_text(k).lower(): as_text(v) for k, v in request.getAllHeaders().items()}


def request_args(request):
    out = {}
    for key, values in request.args.items():
        out[as_text(key)] = [as_text(v) for v in values]
    return out


def client_ip(request):
    getter = getattr(request, "getClientIP", None)
    if getter:
        try:
            value = getter()
            if value:
                return as_text(value)
        except Exception:
            pass
    getter = getattr(request, "getClientAddress", None)
    if getter:
        try:
            address = getter()
            if address is not None:
                return as_text(getattr(address, "host", address))
        except Exception:
            pass
    return ""


def Log(request, path=None, silent=Silent):
    if ServerLog is None:
        return
    path = path if path is not None else '"%s"' % request_path(request)
    ServerLog.write("%s requested %s" % (client_ip(request), path), silent)


class AccessDeniedResource(resource.Resource):
    isLeaf = True
    def render(self, request):
        request.setResponseCode(403)
        request.setHeader(b"content-type", b"text/plain; charset=utf-8")
        return b"403 - Access denied\nUse the server as a Flipnote Studio HTTP proxy and provide X-DSi-SID."


class BannedResource(resource.Resource):
    isLeaf = True
    def render(self, request):
        request.setResponseCode(403)
        request.setHeader(b"content-type", b"text/plain; charset=utf-8")
        return b"403 - This IP address is blocked."


class NotFoundResource(resource.Resource):
    isLeaf = True
    def render(self, request):
        args = request_args(request)
        query = urlencode([(k, v) for k, values in args.items() for v in values])
        path = request_path(request) + (("?" + query) if query else "")
        if ServerLog is not None:
            ServerLog.write('%s got 404 when requesting "%s"' % (client_ip(request), path), Silent)
        request.setResponseCode(404)
        request.setHeader(b"content-type", b"text/plain; charset=utf-8")
        return b"404 - Not Found"


AccessDenied = AccessDeniedResource()
Banned = BannedResource()
NotFound = NotFoundResource()


class Root(resource.Resource):
    isLeaf = False

    def __init__(self, docs_enabled=False):
        super().__init__()
        self.dsResource = DSRoot()
        self.cssResource = static.File("hatenadir/css/")
        self.imagesResource = static.File("hatenadir/images/")
        self.staticResource = static.File("web/static/")
        from webapp import WebRoot
        self.webResource = WebRoot(docs_enabled=docs_enabled)

    def getChild(self, name, request):
        from DB import Database
        if Database.is_ip_banned(client_ip(request)):
            return Banned
        name = as_text(name)
        if name == "css":
            return self.cssResource
        if name == "images":
            return self.imagesResource
        if name == "static":
            return self.staticResource

        headers = request_headers(request)
        host = headers.get("host", "").split(":", 1)[0].lower()
        dsi_host = host in {"flipnote.hatena.com", "ugomemo.hatena.ne.jp"}

        if dsi_host:
            if "x-dsi-sid" not in headers:
                return AccessDenied
            if name == "ds":
                return self.dsResource
            if name == "":
                return self
            return self

        return self.webResource

    def render(self, request):
        from DB import Database
        if Database.is_ip_banned(client_ip(request)):
            return Banned.render(request)
        headers = request_headers(request)
        host = headers.get("host", "").split(":", 1)[0].lower()
        if host not in {"flipnote.hatena.com", "ugomemo.hatena.ne.jp"}:
            return self.webResource.render(request)
        if "x-dsi-sid" not in headers:
            return AccessDenied.render(request)
        request.setHeader(b"content-type", b"text/plain; charset=utf-8")
        return b"RexiMemo OSE\n"


class DSRoot(resource.Resource):
    isLeaf = False
    def __init__(self):
        super().__init__()
        self.region = UgoRoot()
        self.regions = {"v2-xx", "v2-eu", "v2-us", "v2-jp"}

    def getChild(self, name, request):
        name = as_text(name)
        if name in self.regions:
            return self.region
        if name == "":
            return self
        return NotFound

    def render(self, request):
        return b"ds"


class UgoRoot(resource.Resource):
    isLeaf = False
    def __init__(self):
        super().__init__()
        LoadHatenadirStructure(self)

    def getChild(self, name, request):
        text = as_text(name)
        if text == "":
            return self
        if re.fullmatch(r"[0-9A-Fa-f]{16}", text):
            try:
                from DB import Database
                room = Database.get_creator_room_by_fsid(text.upper())
                creator_root = getattr(self, "children", {}).get(b"creator")
                if room and creator_root is not None:
                    return creator_root.getChild(str(room["id"]).encode("ascii"), request)
            except Exception:
                pass
        return NotFound

    def render(self, request):
        return b"ugo"


class FileResource(resource.Resource):
    isLeaf = True
    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath
        self.html = filepath.rsplit(".", 1)[-1][:3].lower() == "htm"

    def render(self, request):
        Log(request)
        if self.html:
            request.setHeader(b"content-type", b"text/html; charset=utf-8")
        return static.File(self.filepath).render(request)


class FolderResource(resource.Resource):
    isLeaf = False
    def getChild(self, name, request):
        return self if as_text(name) == "" else NotFound
    def render(self, request):
        request.setResponseCode(403)
        return b""


def _load_python_resource(filepath):
    module_name = "hatena_dynamic_" + hashlib.sha1(os.path.abspath(filepath).encode("utf-8")).hexdigest()
    spec = importlib.util.spec_from_file_location(module_name, filepath)
    if spec is None or spec.loader is None:
        raise ImportError("Could not load %s" % filepath)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def LoadHatenadirStructure(Resource, path=os.path.join("hatenadir", "ds", "v2-xx")):
    for root, dirs, files in os.walk(path):
        if root != path:
            continue
        for filename in sorted(files, key=lambda f: (f.lower().endswith(".py"), f.lower())):
            filepath = os.path.join(path, filename)
            if filename.endswith(".py"):
                child_name = filename[:-3]
                child = _load_python_resource(os.path.abspath(filepath)).PyResource()
            elif filename.endswith(".pyc"):
                continue
            else:
                child_name = filename
                child = FileResource(filepath)
            Resource.putChild(child_name.encode("utf-8"), child)
            if child_name.endswith(".ugo"):
                Resource.putChild((child_name[:-4] + ".uls").encode("utf-8"), child)
        for foldername in dirs:
            if not foldername.startswith("__"):
                folder = FolderResource()
                LoadHatenadirStructure(folder, os.path.join(path, foldername))
                Resource.putChild(foldername.encode("utf-8"), folder)
        break


def Setup(docs_enabled=False):
    return Root(docs_enabled=docs_enabled)
