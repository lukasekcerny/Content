import sqlite3
from typing import Optional

from app.db.models import Platform, Content, Post, ProfilePicture
from app.constants import PLATFORMS


class Database:
    def __init__(self, db_path: str):
        self._path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()
        self._seed_platforms()

    def _create_tables(self):
        cur = self._conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS platforms (
                id TEXT PRIMARY KEY,
                display_name TEXT,
                connected INTEGER DEFAULT 0,
                username TEXT,
                connected_at TEXT
            );

            CREATE TABLE IF NOT EXISTS content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                file_name TEXT,
                mime_type TEXT,
                file_size INTEGER,
                width INTEGER,
                height INTEGER,
                duration_seconds REAL,
                thumbnail_path TEXT,
                title TEXT,
                description TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id INTEGER REFERENCES content(id) ON DELETE CASCADE,
                platform_id TEXT REFERENCES platforms(id),
                content_type TEXT,
                status TEXT DEFAULT 'draft',
                caption TEXT,
                title TEXT DEFAULT '',
                description TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                scheduled_at TEXT,
                published_at TEXT,
                error_message TEXT,
                remote_id TEXT
            );

            CREATE TABLE IF NOT EXISTS profile_picture (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                file_path TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self._conn.commit()

    def _seed_platforms(self):
        for pid, pdata in PLATFORMS.items():
            self._conn.execute(
                "INSERT OR IGNORE INTO platforms (id, display_name) VALUES (?, ?)",
                (pid, pdata["display_name"]),
            )
        self._conn.commit()

    # --- Platforms ---

    def get_platforms(self) -> list[Platform]:
        rows = self._conn.execute("SELECT * FROM platforms ORDER BY display_name").fetchall()
        return [Platform(**dict(r)) for r in rows]

    def get_platform(self, platform_id: str) -> Optional[Platform]:
        row = self._conn.execute("SELECT * FROM platforms WHERE id = ?", (platform_id,)).fetchone()
        return Platform(**dict(row)) if row else None

    def set_platform_connected(self, platform_id: str, username: str):
        self._conn.execute(
            "UPDATE platforms SET connected = 1, username = ?, connected_at = CURRENT_TIMESTAMP WHERE id = ?",
            (username, platform_id),
        )
        self._conn.commit()

    def set_platform_disconnected(self, platform_id: str):
        self._conn.execute(
            "UPDATE platforms SET connected = 0, username = NULL, connected_at = NULL WHERE id = ?",
            (platform_id,),
        )
        self._conn.commit()

    # --- Content ---

    def add_content(self, c: Content) -> int:
        cur = self._conn.execute(
            """INSERT INTO content
               (file_path, file_name, mime_type, file_size, width, height,
                duration_seconds, thumbnail_path, title, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (c.file_path, c.file_name, c.mime_type, c.file_size,
             c.width, c.height, c.duration_seconds, c.thumbnail_path,
             c.title, c.description),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_all_content(self) -> list[Content]:
        rows = self._conn.execute("SELECT * FROM content ORDER BY created_at DESC").fetchall()
        return [Content(**dict(r)) for r in rows]

    def get_content(self, content_id: int) -> Optional[Content]:
        row = self._conn.execute("SELECT * FROM content WHERE id = ?", (content_id,)).fetchone()
        return Content(**dict(row)) if row else None

    def delete_content(self, content_id: int):
        self._conn.execute("DELETE FROM content WHERE id = ?", (content_id,))
        self._conn.commit()

    def get_content_by_mime_prefix(self, prefix: str) -> list[Content]:
        rows = self._conn.execute(
            "SELECT * FROM content WHERE mime_type LIKE ? ORDER BY created_at DESC",
            (prefix + "%",),
        ).fetchall()
        return [Content(**dict(r)) for r in rows]

    def get_images_only(self) -> list[Content]:
        """Photos only -- excludes GIFs."""
        rows = self._conn.execute(
            "SELECT * FROM content WHERE mime_type LIKE 'image/%' AND mime_type != 'image/gif' ORDER BY created_at DESC"
        ).fetchall()
        return [Content(**dict(r)) for r in rows]

    def update_content(self, c: Content):
        self._conn.execute(
            """UPDATE content SET title=?, description=?, thumbnail_path=?
               WHERE id=?""",
            (c.title, c.description, c.thumbnail_path, c.id),
        )
        self._conn.commit()

    # --- Posts ---

    def add_post(self, p: Post) -> int:
        cur = self._conn.execute(
            """INSERT INTO posts
               (content_id, platform_id, content_type, status, caption,
                title, description, tags, scheduled_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (p.content_id, p.platform_id, p.content_type, p.status,
             p.caption, p.title, p.description, p.tags, p.scheduled_at),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_posts_for_content(self, content_id: int) -> list[Post]:
        rows = self._conn.execute(
            "SELECT * FROM posts WHERE content_id = ?", (content_id,)
        ).fetchall()
        return [Post(**dict(r)) for r in rows]

    def update_post_status(self, post_id: int, status: str, error_message: str = None):
        if status == "published":
            self._conn.execute(
                "UPDATE posts SET status=?, published_at=CURRENT_TIMESTAMP, error_message=NULL WHERE id=?",
                (status, post_id),
            )
        else:
            self._conn.execute(
                "UPDATE posts SET status=?, error_message=? WHERE id=?",
                (status, error_message, post_id),
            )
        self._conn.commit()

    def update_post(self, p: Post):
        self._conn.execute(
            """UPDATE posts SET caption=?, title=?, description=?, tags=?,
               scheduled_at=?, status=? WHERE id=?""",
            (p.caption, p.title, p.description, p.tags,
             p.scheduled_at, p.status, p.id),
        )
        self._conn.commit()

    def delete_post(self, post_id: int):
        self._conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        self._conn.commit()

    def get_scheduled_posts(self) -> list[Post]:
        rows = self._conn.execute(
            "SELECT * FROM posts WHERE status = 'scheduled' AND scheduled_at IS NOT NULL"
        ).fetchall()
        return [Post(**dict(r)) for r in rows]

    # --- Profile Picture ---

    def get_profile_picture(self) -> Optional[ProfilePicture]:
        row = self._conn.execute("SELECT * FROM profile_picture WHERE id = 1").fetchone()
        return ProfilePicture(**{k: row[k] for k in ["file_path", "updated_at"]}) if row else None

    def set_profile_picture(self, file_path: str):
        self._conn.execute(
            """INSERT INTO profile_picture (id, file_path, updated_at)
               VALUES (1, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(id) DO UPDATE SET file_path=excluded.file_path, updated_at=CURRENT_TIMESTAMP""",
            (file_path,),
        )
        self._conn.commit()

    def close(self):
        self._conn.close()
