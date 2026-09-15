from __future__ import annotations

import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def install_twisted_stub():
    if "twisted" in sys.modules:
        return
    if importlib.util.find_spec("twisted") is not None:
        return
    twisted = types.ModuleType("twisted")
    web = types.ModuleType("twisted.web")
    resource_mod = types.ModuleType("twisted.web.resource")
    static_mod = types.ModuleType("twisted.web.static")

    class Resource:
        isLeaf = False
        def __init__(self):
            self.children = {}
        def putChild(self, name, child):
            if not isinstance(name, bytes):
                raise TypeError("child names must be bytes")
            self.children[name] = child
        def getChild(self, name, request):
            return self

    class File(Resource):
        def __init__(self, path):
            super().__init__(); self.path = path
        def render(self, request):
            p = Path(self.path)
            return p.read_bytes() if p.is_file() else b""

    resource_mod.Resource = Resource
    static_mod.File = File
    web.resource = resource_mod
    web.static = static_mod
    twisted.web = web
    sys.modules.update({
        "twisted": twisted,
        "twisted.web": web,
        "twisted.web.resource": resource_mod,
        "twisted.web.static": static_mod,
    })


class ResourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_twisted_stub()
        cls.old_cwd = Path.cwd()
        os.chdir(ROOT)
        import hatena
        cls.root = hatena.Setup()

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.old_cwd)

    def test_dsi_tree_loads(self):
        region = self.root.dsResource.region
        for key in [b"index.ugo", b"index.uls", b"allflipnotes.ugo", b"allflipnotes.uls", b"movie", b"creator", b"comment", b"ch", b"sa"]:
            self.assertIn(key, region.children)

    def test_generated_icons_are_dsi_sized(self):
        image_dir = ROOT / "hatenadir" / "images" / "ds"
        for name in ["browse.ntft", "account.ntft", "room.ntft"]:
            self.assertEqual((image_dir / name).stat().st_size, 2048)


if __name__ == "__main__":
    unittest.main()


class ServerFlagTests(unittest.TestCase):
    def test_docs_flag_is_exact(self):
        import server
        old = list(sys.argv)
        try:
            sys.argv = ["server.py"]
            self.assertFalse(server.docs_enabled_from_args())
            sys.argv = ["server.py", "docs:enabled"]
            self.assertTrue(server.docs_enabled_from_args())
            sys.argv = ["server.py", "docs"]
            self.assertFalse(server.docs_enabled_from_args())
        finally:
            sys.argv = old

class FakeRequest:
    def __init__(self, path=b"/ds/v2-xx/index.ugo", ip="192.0.2.55", headers=None, args=None, body=b""):
        import io
        self.path = path
        self.args = args or {}
        self.content = io.BytesIO(body)
        self._ip = ip
        self._headers = headers or {b"host": b"flipnote.hatena.com", b"x-dsi-sid": b"test"}
        self.response_code = 200
        self.response_headers = {}
    def getClientIP(self): return self._ip
    def getAllHeaders(self): return self._headers
    def setHeader(self, k, v): self.response_headers[k] = v
    def setResponseCode(self, c): self.response_code = c


class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_twisted_stub()
        cls.old_cwd = Path.cwd()
        os.chdir(ROOT)
        import hatena
        cls.root = hatena.Setup()

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.old_cwd)

    def test_index_menu_renders_ugar(self):
        req = FakeRequest()
        data = self.root.dsResource.region.children[b"index.ugo"].render_GET(req)
        self.assertTrue(data.startswith(b"UGAR"))

    def test_browse_menu_renders_ugar(self):
        req = FakeRequest(path=b"/ds/v2-xx/allflipnotes.ugo")
        data = self.root.dsResource.region.children[b"allflipnotes.ugo"].render_GET(req)
        self.assertTrue(data.startswith(b"UGAR"))

class WebRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_twisted_stub()
        cls.old_cwd = Path.cwd()
        os.chdir(ROOT)
        import hatena
        cls.root = hatena.Setup()

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls.old_cwd)

    def web_request(self, path):
        return FakeRequest(path=path.encode(), headers={b"host": b"localhost:8080"})

    def test_home_and_browse_render(self):
        for path in ["/", "/browse", "/about", "/watch/f_sample1", "/creator/r_sample1"]:
            req = self.web_request(path)
            data = self.root.webResource.render_GET(req)
            self.assertIn(b"RexiMemo", data)
            self.assertEqual(req.response_code, 200)

    def test_watch_page_has_fuller_details(self):
        req = self.web_request("/watch/f_sample1")
        data = self.root.webResource.render_GET(req)
        self.assertIn(b"First-frame preview", data)
        self.assertIn(b"File size", data)
        self.assertIn(b"Public ID", data)
        self.assertIn(b"Comments", data)

    def test_docs_are_disabled_by_default(self):
        req = self.web_request("/docs")
        data = self.root.webResource.render_GET(req)
        self.assertEqual(req.response_code, 404)
        self.assertNotIn(b"RexiMemo OSE documentation", data)

    def test_docs_can_be_enabled(self):
        from webapp import WebRoot
        root = WebRoot(docs_enabled=True)
        req = self.web_request("/docs")
        data = root.render_GET(req)
        self.assertEqual(req.response_code, 200)
        self.assertIn(b"RexiMemo OSE documentation", data)
        self.assertIn(b"docs:enabled", data)
        self.assertIn(b"Behaviour", data)
        self.assertIn(b"official RexiMemo DNS service", data)
        self.assertIn(b"Proxy Server", data)
        self.assertIn(b"8080", data)
        self.assertIn(b"release-safety boundary", data)

    def test_thumbnail_render(self):
        req = self.web_request("/thumb/f_sample1.png")
        data = self.root.webResource.render_GET(req)
        self.assertTrue(data.startswith(b"\x89PNG"))
