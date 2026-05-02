"""
cogs/setrole.py  –  ระบบรับยศกดปุ่ม

Admin ตั้งค่า:
  /setrole setup   — ตั้งค่า panel (ห้อง / หัวข้อ / ข้อความ / รูปภาพ)
  /setrole add     — เพิ่มปุ่มรับยศ (อิโมจิ + ชื่อ + role)
  /setrole remove  — ลบปุ่มออก
  /setrole send    — ส่ง (หรืออัพเดต) panel ไปห้องที่ตั้งไว้
  /setrole preview — ดูตัวอย่าง panel ก่อนส่ง (ephemeral)
  /setrole list    — ดูปุ่มทั้งหมด

User: กดปุ่ม → ได้ยศ / กดซ้ำ → ยศหาย (toggle)
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils.database import Database

db = Database()


# ════════════════════════════════════════════════════════════════════════════
#  Helper
# ════════════════════════════════════════════════════════════════════════════

def _build_embed(panel: dict) -> discord.Embed:
    embed = discord.Embed(
        title=panel["title"],
        description=panel["description"],
        color=panel.get("color") or 0x5865F2,
    )
    if panel.get("image_url"):
        embed.set_image(url=panel["image_url"])
    return embed


def _build_view(panel_id: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    for btn in db.rr_get_buttons(panel_id):
        emoji_val = btn["emoji"] or None
        view.add_item(RoleButton(
            panel_id=panel_id,
            btn_id=btn["id"],
            role_id=btn["role_id"],
            label=btn["label"],
            emoji=emoji_val,
        ))
    return view


# ════════════════════════════════════════════════════════════════════════════
#  Button (Persistent)
# ════════════════════════════════════════════════════════════════════════════

class RoleButton(discord.ui.Button):
    def __init__(self, panel_id: int, btn_id: int, role_id: int,
                 label: str, emoji: str | None):
        self.role_id = role_id
        super().__init__(
            label=label,
            emoji=emoji,
            style=discord.ButtonStyle.secondary,
            custom_id=f"sr:{panel_id}:{btn_id}",
        )

    async def callback(self, itx: discord.Interaction):
        role = itx.guild.get_role(self.role_id)
        if not role:
            return await itx.response.send_message(
                "❌ ไม่พบยศนี้ กรุณาแจ้งแอดมิน", ephemeral=True
            )
        if role in itx.user.roles:
            await itx.user.remove_roles(role, reason="setrole toggle")
            await itx.response.send_message(
                f"➖ เอายศ **{role.name}** ออกแล้ว", ephemeral=True
            )
        else:
            await itx.user.add_roles(role, reason="setrole toggle")
            await itx.response.send_message(
                f"✅ ได้รับยศ **{role.name}** แล้ว!", ephemeral=True
            )


# ════════════════════════════════════════════════════════════════════════════
#  Cog
# ════════════════════════════════════════════════════════════════════════════

class SetRoleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """Re-register persistent views หลัง bot restart"""
        with db.conn() as conn:
            rows = conn.execute(
                "SELECT * FROM rr_panels WHERE message_id IS NOT NULL"
            ).fetchall()
        for row in rows:
            self.bot.add_view(_build_view(row["id"]))

    setrole = app_commands.Group(
        name="setrole",
        description="🎭 ระบบรับยศกดปุ่ม",
        default_permissions=discord.Permissions(administrator=True),
    )

    # ── /setrole setup ────────────────────────────────────────────────────
    @setrole.command(name="setup", description="⚙️ ตั้งค่า Panel รับยศ")
    @app_commands.describe(
        channel="ห้องที่จะส่ง Panel",
        title="หัวข้อ",
        description="ข้อความใต้หัวข้อ",
        image_url="URL รูปภาพ (ไม่บังคับ)",
    )
    async def cmd_setup(
        self,
        itx: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        description: str,
        image_url: str = None,
    ):
        guild_id = itx.guild.id

        # เช็คว่ามี panel ของ guild นี้แล้วหรือยัง
        panels = db.rr_list_panels(guild_id)
        if panels:
            panel_id = panels[0]["id"]
            db.rr_update_panel(
                panel_id,
                channel_id=channel.id,
                title=title,
                description=description,
                image_url=image_url,
            )
            action = "อัพเดต"
        else:
            panel_id = db.rr_create_panel(
                guild_id=guild_id,
                channel_id=channel.id,
                title=title,
                description=description,
                image_url=image_url,
            )
            action = "สร้าง"

        embed = discord.Embed(
            title=f"✅ {action} Panel เรียบร้อย!",
            color=0x57F287,
        )
        embed.add_field(name="ห้อง",    value=channel.mention, inline=True)
        embed.add_field(name="หัวข้อ",  value=title,           inline=True)
        embed.add_field(name="ข้อความ", value=description,     inline=False)
        if image_url:
            embed.add_field(name="รูปภาพ", value=image_url, inline=False)
        embed.set_footer(text="ถัดไป: /setrole add เพื่อเพิ่มปุ่มรับยศ")

        await itx.response.send_message(embed=embed, ephemeral=True)

    # ── /setrole add ──────────────────────────────────────────────────────
    @setrole.command(name="add", description="➕ เพิ่มปุ่มรับยศ")
    @app_commands.describe(
        role="Role ที่จะให้เมื่อกดปุ่ม",
        label="ข้อความบนปุ่ม",
        emoji="อิโมจิบนปุ่ม เช่น 🎮 (ไม่บังคับ)",
    )
    async def cmd_add(
        self,
        itx: discord.Interaction,
        role: discord.Role,
        label: str,
        emoji: str = None,
    ):
        panels = db.rr_list_panels(itx.guild.id)
        if not panels:
            return await itx.response.send_message(
                "❌ ยังไม่ได้ตั้งค่า Panel ใช้ `/setrole setup` ก่อน", ephemeral=True
            )

        panel_id = panels[0]["id"]
        btns = db.rr_get_buttons(panel_id)

        if len(btns) >= 25:
            return await itx.response.send_message(
                "❌ มีปุ่มครบ 25 อันแล้ว (Discord limit)", ephemeral=True
            )

        # เช็คซ้ำ
        if any(b["role_id"] == role.id for b in btns):
            return await itx.response.send_message(
                f"❌ {role.mention} มีปุ่มอยู่แล้ว", ephemeral=True
            )

        db.rr_add_button(
            panel_id=panel_id,
            guild_id=itx.guild.id,
            role_id=role.id,
            label=label,
            emoji=emoji,
            sort_order=len(btns),
        )

        await itx.response.send_message(
            f"✅ เพิ่มปุ่ม {emoji or ''} **{label}** → {role.mention} แล้ว\n"
            "ใช้ `/setrole send` เพื่ออัพเดต Panel",
            ephemeral=True,
        )

    # ── /setrole remove ───────────────────────────────────────────────────
    @setrole.command(name="remove", description="🗑️ ลบปุ่มรับยศ")
    @app_commands.describe(role="Role ที่ต้องการลบปุ่มออก")
    async def cmd_remove(self, itx: discord.Interaction, role: discord.Role):
        panels = db.rr_list_panels(itx.guild.id)
        if not panels:
            return await itx.response.send_message("❌ ยังไม่มี Panel", ephemeral=True)

        panel_id = panels[0]["id"]
        btn = db.rr_get_button_by_role(panel_id, role.id)
        if not btn:
            return await itx.response.send_message(
                f"❌ ไม่พบปุ่มสำหรับ {role.mention}", ephemeral=True
            )

        db.rr_remove_button(btn["id"])
        await itx.response.send_message(
            f"✅ ลบปุ่ม **{btn['label']}** ({role.mention}) แล้ว\n"
            "ใช้ `/setrole send` เพื่ออัพเดต Panel",
            ephemeral=True,
        )

    # ── /setrole send ─────────────────────────────────────────────────────
    @setrole.command(name="send", description="📨 ส่ง / อัพเดต Panel ไปห้องที่ตั้งค่าไว้")
    async def cmd_send(self, itx: discord.Interaction):
        panels = db.rr_list_panels(itx.guild.id)
        if not panels:
            return await itx.response.send_message(
                "❌ ยังไม่ได้ตั้งค่า ใช้ `/setrole setup` ก่อน", ephemeral=True
            )

        panel = panels[0]
        btns  = db.rr_get_buttons(panel["id"])
        if not btns:
            return await itx.response.send_message(
                "❌ ยังไม่มีปุ่ม ใช้ `/setrole add` ก่อน", ephemeral=True
            )

        ch = itx.guild.get_channel(panel["channel_id"])
        if not ch:
            return await itx.response.send_message(
                "❌ ไม่พบห้องที่ตั้งค่าไว้ ลอง `/setrole setup` ใหม่", ephemeral=True
            )

        embed = _build_embed(panel)
        view  = _build_view(panel["id"])
        self.bot.add_view(view)

        # ถ้ามี message เก่าอยู่แล้ว → แก้ไข, ไม่งั้น → ส่งใหม่
        if panel.get("message_id"):
            try:
                msg = await ch.fetch_message(panel["message_id"])
                await msg.edit(embed=embed, view=view)
                await itx.response.send_message(
                    f"✅ อัพเดต Panel ใน {ch.mention} แล้ว!", ephemeral=True
                )
                return
            except discord.NotFound:
                pass  # message ถูกลบ → ส่งใหม่

        msg = await ch.send(embed=embed, view=view)
        db.rr_update_panel(panel["id"], message_id=msg.id)
        await itx.response.send_message(
            f"✅ ส่ง Panel ไปที่ {ch.mention} แล้ว!", ephemeral=True
        )

    # ── /setrole preview ──────────────────────────────────────────────────
    @setrole.command(name="preview", description="👁️ ดูตัวอย่าง Panel ก่อนส่ง")
    async def cmd_preview(self, itx: discord.Interaction):
        panels = db.rr_list_panels(itx.guild.id)
        if not panels:
            return await itx.response.send_message("❌ ยังไม่ได้ตั้งค่า", ephemeral=True)

        panel = panels[0]
        embed = _build_embed(panel)
        view  = _build_view(panel["id"])

        await itx.response.send_message(
            "👁️ **ตัวอย่าง Panel** (มองเห็นเฉพาะคุณ)",
            embed=embed,
            view=view,
            ephemeral=True,
        )

    # ── /setrole list ─────────────────────────────────────────────────────
    @setrole.command(name="list", description="📋 ดูปุ่มรับยศทั้งหมด")
    async def cmd_list(self, itx: discord.Interaction):
        panels = db.rr_list_panels(itx.guild.id)
        if not panels:
            return await itx.response.send_message("❌ ยังไม่ได้ตั้งค่า", ephemeral=True)

        panel = panels[0]
        btns  = db.rr_get_buttons(panel["id"])
        ch    = itx.guild.get_channel(panel["channel_id"])

        embed = discord.Embed(title="📋 รายการปุ่มรับยศ", color=0x5865F2)
        embed.add_field(name="ห้อง",   value=ch.mention if ch else "?",         inline=True)
        embed.add_field(name="หัวข้อ", value=panel["title"],                    inline=True)
        embed.add_field(name="สถานะ",  value="📨 ส่งแล้ว" if panel.get("message_id") else "📝 ยังไม่ส่ง", inline=True)

        if btns:
            lines = []
            for b in btns:
                role = itx.guild.get_role(b["role_id"])
                icon = b["emoji"] or "•"
                lines.append(f"{icon} **{b['label']}** → {role.mention if role else '`ไม่พบยศ`'}")
            embed.add_field(name=f"ปุ่ม ({len(btns)})", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="ปุ่ม", value="ยังไม่มีปุ่ม", inline=False)

        embed.set_footer(text="/setrole add เพิ่มปุ่ม • /setrole send อัพเดต Panel")
        await itx.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SetRoleCog(bot))
      
