from __future__ import annotations

import hashlib
import os
import re
import secrets
import sqlite3
import threading
import time
from pathlib import Path

from Hatenatools import TMB

ROOT = Path(__file__).resolve().parent.parent
DATABASE_DIR = ROOT / "database"
CREATORS_DIR = DATABASE_DIR / "Creators"
COMMENTS_DIR = DATABASE_DIR / "Comments"
DEFAULT_DB_PATH = DATABASE_DIR / "reximemo.sqlite3"
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,24}$")


def _now() -> int:
    return int(time.time())


def _row(row):
    return dict(row) if row is not None else None


class DatabaseBackend:
    """Small SQLite backend for RexiMemo: Open Source Edition.

    The OSE deliberately does not contain production session, device, FSID-proof,
    migration, experiment, passkey, Discord or moderation-state tables. Login
    state is just an IP -> account mapping and bans are just blocked IP rows.
    """

    def __init__(self, db_path: str | os.PathLike[str] | None = None):
        DATABASE_DIR.mkdir(parents=True, exist_ok=True)
        CREATORS_DIR.mkdir(parents=True, exist_ok=True)
        COMMENTS_DIR.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path or os.environ.get("REXIMEMO_DB", DEFAULT_DB_PATH))
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.lock = threading.RLock()
        self._schema()
        self._seed()

    def _schema(self):
        with self.lock, self.conn:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS accounts(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_sha256 TEXT NOT NULL,
                    is_admin INTEGER NOT NULL DEFAULT 0 CHECK(is_admin IN (0,1)),
                    created_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ip_logins(
                    ip TEXT PRIMARY KEY,
                    account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
                    last_seen INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ip_bans(
                    ip TEXT PRIMARY KEY,
                    reason TEXT NOT NULL DEFAULT '',
                    created_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS creator_rooms(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    public_id TEXT NOT NULL UNIQUE,
                    account_id INTEGER UNIQUE REFERENCES accounts(id) ON DELETE SET NULL,
                    owner_ip TEXT UNIQUE,
                    fsid TEXT NOT NULL DEFAULT '',
                    display_name TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS channels(
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS flipnotes(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    public_id TEXT NOT NULL UNIQUE,
                    creator_room_id INTEGER NOT NULL REFERENCES creator_rooms(id) ON DELETE CASCADE,
                    creator_fsid TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    channel_id INTEGER REFERENCES channels(id) ON DELETE SET NULL,
                    views INTEGER NOT NULL DEFAULT 0,
                    downloads INTEGER NOT NULL DEFAULT 0,
                    stars INTEGER NOT NULL DEFAULT 0,
                    posted_at INTEGER NOT NULL,
                    deleted INTEGER NOT NULL DEFAULT 0 CHECK(deleted IN (0,1)),
                    UNIQUE(creator_fsid, filename)
                );
                CREATE INDEX IF NOT EXISTS idx_flipnotes_posted ON flipnotes(deleted, posted_at DESC);
                CREATE INDEX IF NOT EXISTS idx_flipnotes_room ON flipnotes(creator_room_id, deleted, posted_at DESC);

                CREATE TABLE IF NOT EXISTS comments(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    public_id TEXT NOT NULL UNIQUE,
                    flipnote_id INTEGER NOT NULL REFERENCES flipnotes(id) ON DELETE CASCADE,
                    creator_room_id INTEGER NOT NULL REFERENCES creator_rooms(id) ON DELETE CASCADE,
                    type TEXT NOT NULL CHECK(type IN ('text','memo')),
                    text_content TEXT,
                    memo_filename TEXT,
                    posted_at INTEGER NOT NULL,
                    deleted INTEGER NOT NULL DEFAULT 0 CHECK(deleted IN (0,1))
                );
                CREATE INDEX IF NOT EXISTS idx_comments_flipnote ON comments(flipnote_id, deleted, posted_at ASC);
                """
            )

    @staticmethod
    def _password_hash(password: str) -> str:
        # Deliberately simple for the OSE reference build. The README warns that
        # this is not production authentication and should be replaced.
        return hashlib.sha256(str(password).encode("utf-8")).hexdigest()

    def _seed(self):
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT OR IGNORE INTO channels(id,title,description) VALUES(1,'General','Public Flipnotes')"
            )
            if not self._one("SELECT id FROM accounts WHERE username=?", ("reximemo",)):
                self.conn.execute(
                    "INSERT INTO accounts(username,password_sha256,is_admin,created_at) VALUES(?,?,1,?)",
                    ("reximemo", self._password_hash("alpine"), _now()),
                )

    def close(self):
        with self.lock:
            self.conn.close()

    def _one(self, sql, args=()):
        return _row(self.conn.execute(sql, args).fetchone())

    def _all(self, sql, args=()):
        return [_row(row) for row in self.conn.execute(sql, args).fetchall()]

    @staticmethod
    def _public_id(prefix: str) -> str:
        return prefix + secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:11]

    # Accounts and the intentionally tiny IP login system -----------------
    def create_account(self, username: str, password: str) -> int:
        username = str(username or "").strip()
        if not USERNAME_RE.fullmatch(username):
            raise ValueError("Use 3-24 letters, numbers, dots, dashes or underscores.")
        if len(str(password or "")) < 4:
            raise ValueError("Password must be at least 4 characters.")
        with self.lock, self.conn:
            try:
                cur = self.conn.execute(
                    "INSERT INTO accounts(username,password_sha256,is_admin,created_at) VALUES(?,?,0,?)",
                    (username, self._password_hash(password), _now()),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("That username is already in use.") from exc
            return int(cur.lastrowid)

    def verify_account(self, username: str, password: str):
        return self._one(
            "SELECT * FROM accounts WHERE username=? AND password_sha256=?",
            (str(username or "").strip(), self._password_hash(password)),
        )

    def get_account(self, account_id: int):
        return self._one("SELECT * FROM accounts WHERE id=?", (int(account_id),))

    def get_account_by_username(self, username: str):
        return self._one("SELECT * FROM accounts WHERE username=?", (str(username or "").strip(),))

    def login_ip(self, ip: str, account_id: int) -> None:
        ip = str(ip or "").strip()
        if not ip:
            raise ValueError("Missing client IP.")
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT INTO ip_logins(ip,account_id,last_seen) VALUES(?,?,?) "
                "ON CONFLICT(ip) DO UPDATE SET account_id=excluded.account_id,last_seen=excluded.last_seen",
                (ip, int(account_id), _now()),
            )

    def logout_ip(self, ip: str) -> None:
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM ip_logins WHERE ip=?", (str(ip or ""),))

    def account_for_ip(self, ip: str):
        ip = str(ip or "").strip()
        if not ip:
            return None
        with self.lock, self.conn:
            row = self._one(
                "SELECT a.* FROM ip_logins l JOIN accounts a ON a.id=l.account_id WHERE l.ip=?",
                (ip,),
            )
            if row:
                self.conn.execute("UPDATE ip_logins SET last_seen=? WHERE ip=?", (_now(), ip))
            return row

    # IP bans --------------------------------------------------------------
    def is_ip_banned(self, ip: str) -> bool:
        return bool(self._one("SELECT ip FROM ip_bans WHERE ip=?", (str(ip or ""),)))

    def ban_ip(self, ip: str, reason: str = "") -> None:
        ip = str(ip or "").strip()
        if not ip:
            raise ValueError("IP is required.")
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT INTO ip_bans(ip,reason,created_at) VALUES(?,?,?) "
                "ON CONFLICT(ip) DO UPDATE SET reason=excluded.reason,created_at=excluded.created_at",
                (ip, str(reason or "")[:200], _now()),
            )
            self.conn.execute("DELETE FROM ip_logins WHERE ip=?", (ip,))

    def unban_ip(self, ip: str) -> None:
        with self.lock, self.conn:
            self.conn.execute("DELETE FROM ip_bans WHERE ip=?", (str(ip or ""),))

    def list_bans(self):
        return self._all("SELECT * FROM ip_bans ORDER BY created_at DESC")

    # Creator rooms --------------------------------------------------------
    @staticmethod
    def _guest_name(ip: str) -> str:
        suffix = hashlib.sha1(str(ip or "guest").encode("utf-8")).hexdigest()[:6].upper()
        return "Guest-" + suffix

    def get_creator_room(self, room_id: int):
        return self._one("SELECT * FROM creator_rooms WHERE id=?", (int(room_id),))

    def get_creator_room_by_public_id(self, public_id: str):
        return self._one("SELECT * FROM creator_rooms WHERE public_id=?", (str(public_id),))

    def get_creator_room_by_fsid(self, fsid: str):
        return self._one("SELECT * FROM creator_rooms WHERE fsid=? ORDER BY id LIMIT 1", (str(fsid or "").upper(),))

    def room_for_account(self, account_id: int):
        return self._one("SELECT * FROM creator_rooms WHERE account_id=?", (int(account_id),))

    def room_for_ip(self, ip: str):
        return self._one("SELECT * FROM creator_rooms WHERE owner_ip=?", (str(ip or ""),))

    def get_or_create_creator(self, ip: str, account_id: int | None = None, *, fsid: str = "", display_name: str = ""):
        fsid = str(fsid or "").upper()[:16]
        if account_id:
            room = self.room_for_account(int(account_id))
            account = self.get_account(int(account_id))
            name = (account or {}).get("username") or str(display_name or "Creator")
            if room:
                if fsid and not room.get("fsid"):
                    with self.lock, self.conn:
                        self.conn.execute("UPDATE creator_rooms SET fsid=? WHERE id=?", (fsid, int(room["id"])))
                    room["fsid"] = fsid
                return room
            with self.lock, self.conn:
                cur = self.conn.execute(
                    "INSERT INTO creator_rooms(public_id,account_id,owner_ip,fsid,display_name,created_at) VALUES(?,?,?,?,?,?)",
                    (self._public_id("r_"), int(account_id), None, fsid, name[:64], _now()),
                )
                return self.get_creator_room(cur.lastrowid)

        ip = str(ip or "").strip()
        room = self.room_for_ip(ip) if ip else None
        if room:
            updates = []
            args = []
            if fsid and not room.get("fsid"):
                updates.append("fsid=?"); args.append(fsid)
            if display_name and room.get("display_name", "").startswith("Guest-"):
                updates.append("display_name=?"); args.append(str(display_name)[:64])
            if updates:
                args.append(int(room["id"]))
                with self.lock, self.conn:
                    self.conn.execute("UPDATE creator_rooms SET %s WHERE id=?" % ",".join(updates), args)
                room = self.get_creator_room(room["id"])
            return room
        name = str(display_name or "").strip()[:64] or self._guest_name(ip)
        with self.lock, self.conn:
            cur = self.conn.execute(
                "INSERT INTO creator_rooms(public_id,account_id,owner_ip,fsid,display_name,created_at) VALUES(?,?,?,?,?,?)",
                (self._public_id("r_"), None, ip or None, fsid, name, _now()),
            )
            return self.get_creator_room(cur.lastrowid)

    def list_creator_flipnotes(self, room_id: int, limit=50, offset=0):
        return self.list_flipnotes(room_id=int(room_id), limit=limit, offset=offset)

    # Channels -------------------------------------------------------------
    def get_channel(self, channel_id: int):
        return self._one("SELECT * FROM channels WHERE id=?", (int(channel_id),))

    def list_channels(self):
        return self._all("SELECT * FROM channels ORDER BY id")

    # Flipnotes ------------------------------------------------------------
    def FlipnotePath(self, creator_fsid: str, filename: str) -> Path:
        return CREATORS_DIR / str(creator_fsid).upper() / (str(filename) + ".ppm")

    def CreatorExists(self, creator_fsid: str) -> bool:
        return bool(self.get_creator_room_by_fsid(creator_fsid) or (CREATORS_DIR / str(creator_fsid).upper()).exists())

    def FlipnoteExists(self, creator_fsid: str, filename: str) -> bool:
        return bool(self.get_flipnote(creator_fsid, filename)) and self.FlipnotePath(creator_fsid, filename).is_file()

    def AddFlipnote(self, content, Channel="1", AccountID=None, ip_address=""):
        data = bytes(content or b"")
        tmb = TMB().Read(data)
        if not tmb:
            return False
        fsid = str(getattr(tmb, "EditorAuthorID", "") or "").upper()
        current_name = str(getattr(tmb, "CurrentFilename", "") or "")
        filename = Path(current_name).stem if current_name else ""
        if not fsid or not filename:
            return False
        if self.get_flipnote(fsid, filename):
            return False
        display_name = str(getattr(tmb, "Username", "") or getattr(tmb, "EditorAuthorName", "") or "Creator")
        room = self.get_or_create_creator(ip_address, AccountID, fsid=fsid, display_name=display_name)
        channel_id = int(Channel) if str(Channel or "").isdigit() else 1
        if not self.get_channel(channel_id):
            channel_id = 1
        now = _now()
        with self.lock, self.conn:
            cur = self.conn.execute(
                "INSERT INTO flipnotes(public_id,creator_room_id,creator_fsid,filename,title,channel_id,posted_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (self._public_id("f_"), int(room["id"]), fsid, filename, "Flipnote by " + room["display_name"], channel_id, now),
            )
            path = self.FlipnotePath(fsid, filename)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return fsid, filename, int(cur.lastrowid)

    def get_flipnote(self, creator_fsid: str, filename: str):
        return self._one(
            "SELECT f.*,r.public_id AS creator_public_id,r.display_name AS creator_name,r.account_id,r.owner_ip "
            "FROM flipnotes f JOIN creator_rooms r ON r.id=f.creator_room_id "
            "WHERE f.creator_fsid=? AND f.filename=? AND f.deleted=0",
            (str(creator_fsid).upper(), str(filename)),
        )

    def get_flipnote_by_id(self, flipnote_id: int):
        return self._one(
            "SELECT f.*,r.public_id AS creator_public_id,r.display_name AS creator_name,r.account_id,r.owner_ip "
            "FROM flipnotes f JOIN creator_rooms r ON r.id=f.creator_room_id WHERE f.id=? AND f.deleted=0",
            (int(flipnote_id),),
        )

    def get_flipnote_by_public_id(self, public_id: str):
        return self._one(
            "SELECT f.*,r.public_id AS creator_public_id,r.display_name AS creator_name,r.account_id,r.owner_ip "
            "FROM flipnotes f JOIN creator_rooms r ON r.id=f.creator_room_id WHERE f.public_id=? AND f.deleted=0",
            (str(public_id),),
        )

    def GetFlipnote(self, CreatorID, filename, Store=False):
        return self.get_flipnote(CreatorID, filename) or False

    def GetFlipnotePPM(self, CreatorID, filename):
        return self.FlipnotePath(CreatorID, filename).read_bytes()

    def GetFlipnoteTMB(self, CreatorID, filename):
        with self.FlipnotePath(CreatorID, filename).open("rb") as f:
            return f.read(0x6A0)

    def list_flipnotes(self, *, sort="new", page=1, per_page=50, limit=None, offset=None, channel_id=None, room_id=None):
        if limit is None:
            limit = per_page
        if offset is None:
            offset = max(0, int(page) - 1) * int(per_page)
        order = {
            "new": "f.posted_at DESC, f.id DESC",
            "popular": "f.views DESC, f.stars DESC, f.posted_at DESC",
            "top": "f.stars DESC, f.views DESC, f.posted_at DESC",
        }.get(sort, "f.posted_at DESC, f.id DESC")
        where = ["f.deleted=0"]
        args = []
        if channel_id is not None:
            where.append("f.channel_id=?"); args.append(int(channel_id))
        if room_id is not None:
            where.append("f.creator_room_id=?"); args.append(int(room_id))
        args.extend((int(limit), int(offset)))
        return self._all(
            "SELECT f.*,r.public_id AS creator_public_id,r.display_name AS creator_name,r.account_id,r.owner_ip "
            "FROM flipnotes f JOIN creator_rooms r ON r.id=f.creator_room_id "
            "WHERE %s ORDER BY %s LIMIT ? OFFSET ?" % (" AND ".join(where), order), args,
        )

    def count_flipnotes(self, *, channel_id=None, room_id=None):
        where = ["deleted=0"]
        args = []
        if channel_id is not None:
            where.append("channel_id=?"); args.append(int(channel_id))
        if room_id is not None:
            where.append("creator_room_id=?"); args.append(int(room_id))
        row = self._one("SELECT COUNT(*) AS n FROM flipnotes WHERE " + " AND ".join(where), args)
        return int(row["n"] if row else 0)

    @property
    def Newest(self):
        return [(r["creator_fsid"], r["filename"]) for r in self.list_flipnotes(limit=5000)]

    @property
    def Views(self):
        row = self._one("SELECT COALESCE(SUM(views),0) AS n FROM flipnotes WHERE deleted=0")
        return int(row["n"])

    @property
    def Stars(self):
        row = self._one("SELECT COALESCE(SUM(stars),0) AS n FROM flipnotes WHERE deleted=0")
        return int(row["n"])

    def AddView(self, CreatorID, filename, AccountID=None):
        with self.lock, self.conn:
            cur = self.conn.execute(
                "UPDATE flipnotes SET views=views+1 WHERE creator_fsid=? AND filename=? AND deleted=0",
                (str(CreatorID).upper(), str(filename)),
            )
            return cur.rowcount > 0

    def AddDownload(self, CreatorID, filename):
        with self.lock, self.conn:
            cur = self.conn.execute(
                "UPDATE flipnotes SET downloads=downloads+1 WHERE creator_fsid=? AND filename=? AND deleted=0",
                (str(CreatorID).upper(), str(filename)),
            )
            return cur.rowcount > 0

    def AddStar(self, CreatorID, filename, amount=1, color="yellow"):
        try:
            amount = max(1, min(65535, int(amount)))
        except Exception:
            return False
        with self.lock, self.conn:
            cur = self.conn.execute(
                "UPDATE flipnotes SET stars=stars+? WHERE creator_fsid=? AND filename=? AND deleted=0",
                (amount, str(CreatorID).upper(), str(filename)),
            )
            return cur.rowcount > 0

    def delete_flipnote(self, flipnote_id: int) -> bool:
        with self.lock, self.conn:
            cur = self.conn.execute("UPDATE flipnotes SET deleted=1 WHERE id=?", (int(flipnote_id),))
            return cur.rowcount > 0

    # Comments -------------------------------------------------------------
    def add_text_comment(self, flipnote_id: int, text: str, *, ip_address="", account_id=None):
        text = " ".join(str(text or "").split())[:500]
        if not text:
            raise ValueError("Comment is empty.")
        room = self.get_or_create_creator(ip_address, account_id)
        with self.lock, self.conn:
            cur = self.conn.execute(
                "INSERT INTO comments(public_id,flipnote_id,creator_room_id,type,text_content,posted_at) VALUES(?,?,?,?,?,?)",
                (self._public_id("m_"), int(flipnote_id), int(room["id"]), "text", text, _now()),
            )
            return int(cur.lastrowid)

    def add_memo_comment(self, flipnote_id: int, ppm: bytes, *, ip_address="", account_id=None):
        data = bytes(ppm or b"")
        tmb = TMB().Read(data)
        if not tmb:
            raise ValueError("Invalid mini Flipnote.")
        room = self.get_or_create_creator(
            ip_address,
            account_id,
            fsid=str(getattr(tmb, "EditorAuthorID", "") or ""),
            display_name=str(getattr(tmb, "Username", "") or ""),
        )
        with self.lock, self.conn:
            cur = self.conn.execute(
                "INSERT INTO comments(public_id,flipnote_id,creator_room_id,type,memo_filename,posted_at) VALUES(?,?,?,?,?,?)",
                (self._public_id("m_"), int(flipnote_id), int(room["id"]), "memo", "pending", _now()),
            )
            cid = int(cur.lastrowid)
            name = f"{cid}.ppm"
            (COMMENTS_DIR / name).write_bytes(data)
            self.conn.execute("UPDATE comments SET memo_filename=? WHERE id=?", (name, cid))
            return cid

    def get_comment(self, comment_id: int):
        return self._one(
            "SELECT c.*,r.public_id AS creator_public_id,r.display_name AS creator_name "
            "FROM comments c JOIN creator_rooms r ON r.id=c.creator_room_id WHERE c.id=? AND c.deleted=0",
            (int(comment_id),),
        )

    def list_comments(self, flipnote_id: int, limit=100, offset=0):
        return self._all(
            "SELECT c.*,r.public_id AS creator_public_id,r.display_name AS creator_name "
            "FROM comments c JOIN creator_rooms r ON r.id=c.creator_room_id "
            "WHERE c.flipnote_id=? AND c.deleted=0 ORDER BY c.posted_at ASC,c.id ASC LIMIT ? OFFSET ?",
            (int(flipnote_id), int(limit), int(offset)),
        )

    def count_comments(self, flipnote_id: int):
        row = self._one("SELECT COUNT(*) AS n FROM comments WHERE flipnote_id=? AND deleted=0", (int(flipnote_id),))
        return int(row["n"] if row else 0)

    def comment_ppm(self, comment_id: int):
        row = self.get_comment(comment_id)
        if not row or row["type"] != "memo" or not row.get("memo_filename"):
            return None
        path = COMMENTS_DIR / row["memo_filename"]
        return path.read_bytes() if path.is_file() else None

    # Minimal admin helpers ------------------------------------------------
    def recent_ip_logins(self, limit=50):
        return self._all(
            "SELECT l.ip,l.last_seen,a.id AS account_id,a.username FROM ip_logins l "
            "JOIN accounts a ON a.id=l.account_id ORDER BY l.last_seen DESC LIMIT ?",
            (int(limit),),
        )


Database = DatabaseBackend()
