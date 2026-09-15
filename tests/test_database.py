import tempfile
import unittest
from pathlib import Path

from database import DatabaseBackend


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = DatabaseBackend(Path(self.temp.name) / "test.sqlite3")

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_default_admin(self):
        account = self.db.verify_account("reximemo", "alpine")
        self.assertIsNotNone(account)
        self.assertEqual(account["is_admin"], 1)

    def test_ip_login_and_logout(self):
        aid = self.db.create_account("tester", "pass")
        self.db.login_ip("192.0.2.10", aid)
        self.assertEqual(self.db.account_for_ip("192.0.2.10")["username"], "tester")
        self.db.logout_ip("192.0.2.10")
        self.assertIsNone(self.db.account_for_ip("192.0.2.10"))

    def test_guest_room_is_stable_per_ip(self):
        first = self.db.get_or_create_creator("192.0.2.20", fsid="A000000000000010", display_name="Guest")
        second = self.db.get_or_create_creator("192.0.2.20", fsid="A000000000000011", display_name="Other")
        self.assertEqual(first["id"], second["id"])

    def test_ip_ban(self):
        self.db.ban_ip("192.0.2.30", "test")
        self.assertTrue(self.db.is_ip_banned("192.0.2.30"))
        self.db.unban_ip("192.0.2.30")
        self.assertFalse(self.db.is_ip_banned("192.0.2.30"))


if __name__ == "__main__":
    unittest.main()
