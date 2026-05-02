import sqlite3
from datetime import datetime
from typing import Optional


class Database:
    def __init__(self, path: str = "tickets.db"):
        self.path = path
        self._init()

    # ── Connection ──────────────────────────────────────────────────────
    def conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    # ── Schema ──────────────────────────────────────────────────────────
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
                guild_id             INTEGER PRIMARY KEY,
                support_role_id      INTEGER,
                admin_role_id        INTEGER,
                vip_role_id          INTEGER,
                ticket_category_id   INTEGER,
                log_channel_id       INTEGER,
                transcript_channel_id INTEGER,
                cooldown_seconds     INTEGER DEFAULT 300,
                language             TEXT    DEFAULT 'th',
                panel_message_id     INTEGER
            );

            -- Migration: add vip_role_id if not exists (safe for existing DBs)
            CREATE TABLE IF NOT EXISTS _migrations (key TEXT PRIMARY KEY);
            

            CREATE TABLE IF NOT EXISTS cooldowns (
                user_id    INTEGER,
                guild_id   INTEGER,
                last_ticket TEXT,
                PRIMARY KEY (user_id, guild_id)
            );

            -- ระบบรับยศ: กลุ่มหลัก (เช่น "จุดประสงค์", "ประเภทซื้อขาย")
            CREATE TABLE IF NOT EXISTS role_groups (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                group_key   TEXT    NOT NULL,   -- internal key เช่น 'purpose', 'trade'
                label       TEXT    NOT NULL,   -- ชื่อที่แสดง เช่น '🎯 จุดประสงค์'
                description TEXT,
                parent_key  TEXT,               -- ถ้าเป็น submenu ให้ใส่ group_key ของ parent
                trigger_option_key TEXT,        -- option key ของ parent ที่ trigger submenu นี้
                sort_order  INTEGER DEFAULT 0,
                UNIQUE(guild_id, group_key)
            );

            -- ระบบรับยศ: ตัวเลือกแต่ละอัน + role ที่จะให้
            CREATE TABLE IF NOT EXISTS role_options (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    INTEGER NOT NULL,
                group_key   TEXT    NOT NULL,
                option_key  TEXT    NOT NULL,   -- internal key เช่น 'find_friend'
                label       TEXT    NOT NULL,   -- ชื่อที่แสดงบนปุ่ม เช่น '👥 หาเพื่อน'
                emoji       TEXT,
                role_id     INTEGER,            -- Discord Role ID ที่จะให้/เอาออก
                has_submenu INTEGER DEFAULT 0,  -- 1 = มี submenu ให้เลือกต่อ
                sort_order  INTEGER DEFAULT 0,
                UNIQUE(guild_id, group_key, option_key)
            );

            -- บันทึก panel message id สำหรับระบบรับยศ (setrole)
            CREATE TABLE IF NOT EXISTS role_panels (
                guild_id    INTEGER NOT NULL,
                channel_id  INTEGER NOT NULL,
                message_id  INTEGER NOT NULL,
                PRIMARY KEY (guild_id, channel_id)
            );

            -- ระบบ RoleReact: panel กดปุ่มรับยศแบบอิสระ
            CREATE TABLE IF NOT EXISTS rr_panels (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id     INTEGER NOT NULL,
                channel_id   INTEGER NOT NULL,
                message_id   INTEGER,
                title        TEXT    NOT NULL DEFAULT 'รับยศ',
                description  TEXT    NOT NULL DEFAULT 'กดปุ่มด้านล่างเพื่อรับยศ',
                image_url    TEXT,
                color        INTEGER DEFAULT 5793266,
                created_at   TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rr_buttons (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                panel_id     INTEGER NOT NULL,
                guild_id     INTEGER NOT NULL,
                role_id      INTEGER NOT NULL,
                label        TEXT    NOT NULL,
                emoji        TEXT,
                style        TEXT    DEFAULT 'secondary',
                sort_order   INTEGER DEFAULT 0
            );
            """)
            # Migration: เพิ่ม vip_role_id สำหรับ DB เก่าที่ยังไม่มี column นี้
            try:
                db.execute("ALTER TABLE guild_config ADD COLUMN vip_role_id INTEGER")
            except Exception:
                pass  # column มีอยู่แล้ว

    # ── Tickets ─────────────────────────────────────────────────────────
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
                "SELECT * FROM tickets WHERE channel_id = ?", (channel_id,)
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

    # ── Stats ────────────────────────────────────────────────────────────
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

    # ── Guild Config ─────────────────────────────────────────────────────
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

    # ── Cooldown ─────────────────────────────────────────────────────────
    def check_cooldown(self, user_id: int, guild_id: int,
                       cooldown_secs: int = 300) -> float:
        """Returns remaining seconds (0 = no cooldown active)."""
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

    # ── Role System ──────────────────────────────────────────────────────

    def get_role_groups(self, guild_id: int, parent_key: str | None = None) -> list[dict]:
        with self.conn() as db:
            if parent_key is None:
                rows = db.execute(
                    "SELECT * FROM role_groups WHERE guild_id=? AND parent_key IS NULL ORDER BY sort_order",
                    (guild_id,)
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM role_groups WHERE guild_id=? AND parent_key=? ORDER BY sort_order",
                    (guild_id, parent_key)
                ).fetchall()
            return [dict(r) for r in rows]

    def get_role_options(self, guild_id: int, group_key: str) -> list[dict]:
        with self.conn() as db:
            rows = db.execute(
                "SELECT * FROM role_options WHERE guild_id=? AND group_key=? ORDER BY sort_order",
                (guild_id, group_key)
            ).fetchall()
            return [dict(r) for r in rows]

    def upsert_role_group(self, guild_id: int, group_key: str, label: str,
                          description: str = "", parent_key: str | None = None,
                          trigger_option_key: str | None = None, sort_order: int = 0):
        with self.conn() as db:
            db.execute("""
                INSERT INTO role_groups (guild_id, group_key, label, description, parent_key, trigger_option_key, sort_order)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(guild_id, group_key) DO UPDATE SET
                    label=excluded.label,
                    description=excluded.description,
                    parent_key=excluded.parent_key,
                    trigger_option_key=excluded.trigger_option_key,
                    sort_order=excluded.sort_order
            """, (guild_id, group_key, label, description, parent_key, trigger_option_key, sort_order))

    def upsert_role_option(self, guild_id: int, group_key: str, option_key: str,
                           label: str, emoji: str = "", role_id: int | None = None,
                           has_submenu: bool = False, sort_order: int = 0):
        with self.conn() as db:
            db.execute("""
                INSERT INTO role_options (guild_id, group_key, option_key, label, emoji, role_id, has_submenu, sort_order)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(guild_id, group_key, option_key) DO UPDATE SET
                    label=excluded.label,
                    emoji=excluded.emoji,
                    role_id=excluded.role_id,
                    has_submenu=excluded.has_submenu,
                    sort_order=excluded.sort_order
            """, (guild_id, group_key, option_key, label, emoji, role_id, int(has_submenu), sort_order))

    def delete_role_option(self, guild_id: int, group_key: str, option_key: str):
        with self.conn() as db:
            db.execute(
                "DELETE FROM role_options WHERE guild_id=? AND group_key=? AND option_key=?",
                (guild_id, group_key, option_key)
            )

    def delete_role_group(self, guild_id: int, group_key: str):
        with self.conn() as db:
            db.execute("DELETE FROM role_groups WHERE guild_id=? AND group_key=?", (guild_id, group_key))
            db.execute("DELETE FROM role_options WHERE guild_id=? AND group_key=?", (guild_id, group_key))

    def save_role_panel(self, guild_id: int, channel_id: int, message_id: int):
        with self.conn() as db:
            db.execute("""
                INSERT OR REPLACE INTO role_panels (guild_id, channel_id, message_id)
                VALUES (?,?,?)
            """, (guild_id, channel_id, message_id))

    def get_role_panel(self, guild_id: int) -> Optional[dict]:
        with self.conn() as db:
            row = db.execute(
                "SELECT * FROM role_panels WHERE guild_id=?", (guild_id,)
            ).fetchone()
            return dict(row) if row else None

    # ── RoleReact System ─────────────────────────────────────────────────

    def rr_create_panel(self, guild_id: int, channel_id: int,
                        title: str, description: str,
                        image_url: str = None, color: int = 5793266) -> int:
        with self.conn() as db:
            cur = db.execute("""
                INSERT INTO rr_panels (guild_id, channel_id, title, description, image_url, color, created_at)
                VALUES (?,?,?,?,?,?,?)
            """, (guild_id, channel_id, title, description, image_url, color,
                  datetime.now().isoformat()))
            return cur.lastrowid

    def rr_update_panel(self, panel_id: int, **kwargs):
        with self.conn() as db:
            sets = ", ".join(f"{k}=?" for k in kwargs)
            db.execute(
                f"UPDATE rr_panels SET {sets} WHERE id=?",
                (*kwargs.values(), panel_id)
            )

    def rr_get_panel(self, panel_id: int) -> Optional[dict]:
        with self.conn() as db:
            row = db.execute("SELECT * FROM rr_panels WHERE id=?", (panel_id,)).fetchone()
            return dict(row) if row else None

    def rr_get_panel_by_message(self, message_id: int) -> Optional[dict]:
        with self.conn() as db:
            row = db.execute(
                "SELECT * FROM rr_panels WHERE message_id=?", (message_id,)
            ).fetchone()
            return dict(row) if row else None

    def rr_list_panels(self, guild_id: int) -> list[dict]:
        with self.conn() as db:
            rows = db.execute(
                "SELECT * FROM rr_panels WHERE guild_id=? ORDER BY id DESC", (guild_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def rr_delete_panel(self, panel_id: int):
        with self.conn() as db:
            db.execute("DELETE FROM rr_buttons WHERE panel_id=?", (panel_id,))
            db.execute("DELETE FROM rr_panels WHERE id=?", (panel_id,))

    def rr_add_button(self, panel_id: int, guild_id: int, role_id: int,
                      label: str, emoji: str = None,
                      style: str = "secondary", sort_order: int = 0) -> int:
        with self.conn() as db:
            cur = db.execute("""
                INSERT INTO rr_buttons (panel_id, guild_id, role_id, label, emoji, style, sort_order)
                VALUES (?,?,?,?,?,?,?)
            """, (panel_id, guild_id, role_id, label, emoji, style, sort_order))
            return cur.lastrowid

    def rr_get_buttons(self, panel_id: int) -> list[dict]:
        with self.conn() as db:
            rows = db.execute(
                "SELECT * FROM rr_buttons WHERE panel_id=? ORDER BY sort_order, id",
                (panel_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def rr_remove_button(self, button_id: int):
        with self.conn() as db:
            db.execute("DELETE FROM rr_buttons WHERE id=?", (button_id,))

    def rr_get_button_by_role(self, panel_id: int, role_id: int) -> Optional[dict]:
        with self.conn() as db:
            row = db.execute(
                "SELECT * FROM rr_buttons WHERE panel_id=? AND role_id=?",
                (panel_id, role_id)
            ).fetchone()
            return dict(row) if row else None
