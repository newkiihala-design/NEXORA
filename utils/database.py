import sqlite3
from datetime import datetime
from typing import Optional


class Database:
    def __init__(self, path: str = "tickets.db"):
        self.path = path
        self._init()

    def conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def _init(self):
        with self.conn() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS tickets (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id     TEXT    UNIQUE,
                guild_id      INTEGER NOT NULL,
                channel_id    INTEGER NOT NULL,
                user_id       INTEGER NOT NULL,
                category      TEXT    NOT NULL,
                priority      TEXT    DEFAULT 'normal',
                status        TEXT    DEFAULT 'open',
                assigned_to   INTEGER,
                created_at    TEXT    NOT NULL,
                closed_at     TEXT,
                rating        INTEGER
            );

            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id              INTEGER PRIMARY KEY,
                support_role_id       INTEGER,
                admin_role_id         INTEGER,
                vip_role_id           INTEGER,
                ticket_category_id    INTEGER,
                log_channel_id        INTEGER,
                transcript_channel_id INTEGER,
                cooldown_seconds      INTEGER DEFAULT 300,
                language              TEXT    DEFAULT 'th',
                panel_message_id      INTEGER
            );

            CREATE TABLE IF NOT EXISTS cooldowns (
                user_id     INTEGER,
                guild_id    INTEGER,
                last_ticket TEXT,
                PRIMARY KEY (user_id, guild_id)
            );

            -- ระบบรับยศ: ตั้งครั้งเดียว 1 guild = 1 panel
            CREATE TABLE IF NOT EXISTS setrole (
                guild_id    INTEGER PRIMARY KEY,
                channel_id  INTEGER NOT NULL,
                message_id  INTEGER,
                role_id     INTEGER NOT NULL,
                emoji       TEXT    NOT NULL,
                title       TEXT    NOT NULL,
                description TEXT    NOT NULL,
                image_url   TEXT
            );
            """)
            # migration สำหรับ DB เก่า
            for col in ["vip_role_id"]:
                try:
                    db.execute(f"ALTER TABLE guild_config ADD COLUMN {col} INTEGER")
                except Exception:
                    pass

    # ── Tickets ──────────────────────────────────────────────────────────
    def create_ticket(self, ticket_id, guild_id, channel_id,
                      user_id, category, priority="normal"):
        with self.conn() as db:
            db.execute("""
                INSERT INTO tickets
                    (ticket_id, guild_id, channel_id, user_id, category, priority, created_at)
                VALUES (?,?,?,?,?,?,?)
            """, (ticket_id, guild_id, channel_id, user_id, category, priority,
                  datetime.now().isoformat()))

    def get_ticket(self, channel_id: int) -> Optional[dict]:
        with self.conn() as db:
            row = db.execute(
                "SELECT * FROM tickets WHERE channel_id=?", (channel_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_user_open_ticket(self, guild_id: int, user_id: int) -> Optional[dict]:
        with self.conn() as db:
            row = db.execute("""
                SELECT * FROM tickets
                WHERE guild_id=? AND user_id=? AND status='open'
                ORDER BY id DESC LIMIT 1
            """, (guild_id, user_id)).fetchone()
            return dict(row) if row else None

    def close_ticket(self, channel_id: int):
        with self.conn() as db:
            db.execute("""
                UPDATE tickets SET status='closed', closed_at=?
                WHERE channel_id=?
            """, (datetime.now().isoformat(), channel_id))

    def assign_ticket(self, channel_id: int, admin_id: int):
        with self.conn() as db:
            db.execute(
                "UPDATE tickets SET assigned_to=? WHERE channel_id=?",
                (admin_id, channel_id)
            )

    def set_priority(self, channel_id: int, priority: str):
        with self.conn() as db:
            db.execute(
                "UPDATE tickets SET priority=? WHERE channel_id=?",
                (priority, channel_id)
            )

    def rate_ticket(self, channel_id: int, rating: int):
        with self.conn() as db:
            db.execute(
                "UPDATE tickets SET rating=? WHERE channel_id=?",
                (rating, channel_id)
            )

    # ── Stats ─────────────────────────────────────────────────────────────
    def get_stats(self, guild_id: int) -> dict:
        with self.conn() as db:
            row = db.execute("""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN status='open'   THEN 1 ELSE 0 END) AS open_count,
                    SUM(CASE WHEN status='closed' THEN 1 ELSE 0 END) AS closed_count,
                    AVG(CAST(rating AS REAL)) AS avg_rating
                FROM tickets WHERE guild_id=?
            """, (guild_id,)).fetchone()
            return dict(row) if row else {}

    def get_open_tickets(self, guild_id: int) -> list[dict]:
        with self.conn() as db:
            rows = db.execute(
                "SELECT * FROM tickets WHERE guild_id=? AND status='open' ORDER BY id DESC",
                (guild_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_ticket_count(self, guild_id: int) -> int:
        with self.conn() as db:
            row = db.execute(
                "SELECT COUNT(*) FROM tickets WHERE guild_id=?", (guild_id,)
            ).fetchone()
            return row[0] if row else 0

    # ── Guild Config ──────────────────────────────────────────────────────
    def get_config(self, guild_id: int) -> Optional[dict]:
        with self.conn() as db:
            row = db.execute(
                "SELECT * FROM guild_config WHERE guild_id=?", (guild_id,)
            ).fetchone()
            return dict(row) if row else None

    def set_config(self, guild_id: int, **kwargs):
        with self.conn() as db:
            exists = db.execute(
                "SELECT 1 FROM guild_config WHERE guild_id=?", (guild_id,)
            ).fetchone()
            if exists:
                sets = ", ".join(f"{k}=?" for k in kwargs)
                db.execute(
                    f"UPDATE guild_config SET {sets} WHERE guild_id=?",
                    (*kwargs.values(), guild_id)
                )
            else:
                kwargs["guild_id"] = guild_id
                cols = ", ".join(kwargs.keys())
                vals = ", ".join("?" * len(kwargs))
                db.execute(
                    f"INSERT INTO guild_config ({cols}) VALUES ({vals})",
                    list(kwargs.values())
                )

    # ── Cooldown ──────────────────────────────────────────────────────────
    def check_cooldown(self, user_id: int, guild_id: int,
                       cooldown_secs: int = 300) -> float:
        with self.conn() as db:
            row = db.execute(
                "SELECT last_ticket FROM cooldowns WHERE user_id=? AND guild_id=?",
                (user_id, guild_id)
            ).fetchone()
            if row:
                last = datetime.fromisoformat(row[0])
                elapsed = (datetime.now() - last).total_seconds()
                if elapsed < cooldown_secs:
                    return cooldown_secs - elapsed
        return 0.0

    def set_cooldown(self, user_id: int, guild_id: int):
        with self.conn() as db:
            db.execute("""
                INSERT OR REPLACE INTO cooldowns (user_id, guild_id, last_ticket)
                VALUES (?,?,?)
            """, (user_id, guild_id, datetime.now().isoformat()))

    # ── SetRole ───────────────────────────────────────────────────────────
    def setrole_save(self, guild_id: int, channel_id: int, role_id: int,
                     emoji: str, title: str, description: str,
                     image_url: str = None):
        with self.conn() as db:
            db.execute("""
                INSERT INTO setrole
                    (guild_id, channel_id, role_id, emoji, title, description, image_url)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(guild_id) DO UPDATE SET
                    channel_id=excluded.channel_id,
                    role_id=excluded.role_id,
                    emoji=excluded.emoji,
                    title=excluded.title,
                    description=excluded.description,
                    image_url=excluded.image_url,
                    message_id=NULL
            """, (guild_id, channel_id, role_id, emoji, title, description, image_url))

    def setrole_get(self, guild_id: int) -> Optional[dict]:
        with self.conn() as db:
            row = db.execute(
                "SELECT * FROM setrole WHERE guild_id=?", (guild_id,)
            ).fetchone()
            return dict(row) if row else None

    def setrole_set_message(self, guild_id: int, message_id: int):
        with self.conn() as db:
            db.execute(
                "UPDATE setrole SET message_id=? WHERE guild_id=?",
                (message_id, guild_id)
        )
