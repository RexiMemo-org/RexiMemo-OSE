import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReleaseShapeTests(unittest.TestCase):
    def test_no_secret_or_font_files(self):
        blocked_ext = {".pem", ".key", ".crt", ".p12", ".pfx", ".ttf", ".otf", ".woff", ".woff2"}
        bad = []
        for path in ROOT.rglob("*"):
            if path.is_file() and path.suffix.lower() in blocked_ext:
                bad.append(str(path.relative_to(ROOT)))
        self.assertEqual(bad, [])

    def test_removed_production_components_are_absent(self):
        for name in ["discord_bot.py", "network_services.py", "ssl3_compat.py", "packet_capture.py", "ppmverify.py", "fnkey.pem", "token.txt"]:
            self.assertFalse((ROOT / name).exists(), name)

    def test_exactly_three_sample_flipnotes(self):
        samples = list((ROOT / "database" / "Creators").glob("*/*.ppm"))
        self.assertEqual(len(samples), 3)

    def test_github_docs_copy_and_connection_guidance(self):
        docs = (ROOT / "DOCS.md").read_text()
        self.assertIn("official RexiMemo DNS service", docs)
        self.assertIn("Proxy Server", docs)
        self.assertIn("port to `8080`", docs)
        self.assertIn("release-safety boundary", docs)
        self.assertIn("Account security notice", docs)
        self.assertIn("IP login notice", docs)

    def test_ose_web_branding(self):
        logo = ROOT / "web" / "static" / "RexiMemo_OSE_Logo.png"
        self.assertTrue(logo.is_file())
        css = (ROOT / "web" / "static" / "site.css").read_text().lower()
        self.assertIn("#b13b29", css)
        self.assertNotIn("#ae301f", css)
        webapp = (ROOT / "webapp.py").read_text()
        self.assertIn("OSE login state is tied to your IP address.", webapp)
        self.assertNotIn("It is intentionally not a production session system.", webapp)


if __name__ == "__main__":
    unittest.main()
