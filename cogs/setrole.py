"""
cogs/setrole.py  —  ระบบรับยศกดปุ่ม (ใหม่)

Admin ใช้คำสั่งเดียวจบ:
  /setrole channel:#ห้อง role:@ยศ emoji:🎮 label:ข้อความ image:URL

→ ส่ง Embed พร้อมปุ่มรับยศไปยังห้องที่เลือกทันที ไม่ต้องทำขั้นตอนเพิ่ม
→ กดปุ่มอีกครั้ง = ถอดยศ (toggle)
→ ปุ่มยังคงใช้งานได้หลัง bot restart
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils.database import Database

db = Database()


# ════════════════════════════════════════════════════════════════════════════
#  Persistent Button
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


def _rebuild_view(panel_id: int) -> discord.ui.View:
    """สร้าง View จาก DB สำหรับ persistent view หลัง restart"""
    view = discord.ui.View(timeout=None)
    for btn in db.rr_get_buttons(panel_id):
        view.add_item(RoleButton(
            panel_id=panel_id,
            btn_id=btn["id"],
            role_id=btn["role_id"],
            label=btn["label"],
            emoji=btn["emoji"] or None,
        ))
    return view


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
            self.bot.add_view(_rebuild_view(row["id"]))

    # ── /setrole ──────────────────────────────────────────────────────────
    @app_commands.command(
        name="setrole",
        description="🎭 สร้างปุ่มรับยศและส่งไปยังห้องที่เลือกทันที"
    )
    @app_commands.describe(
        channel="ห้องที่จะส่งปุ่มรับยศ",
        role="ยศที่จะให้เมื่อกดปุ่ม",
        emoji="อิโมจิบนปุ่ม เช่น 🎮 (ไม่บังคับ)",
        label="ข้อความบนปุ่มและหัวข้อ Embed",
        image="URL รูปภาพใน Embed (ไม่บังคับ)",
    )
    @app_commands.default_permissions(administrator=True)
    async def setrole(
        self,
        itx: discord.Interaction,
        channel: discord.TextChannel,
        role: discord.Role,
        label: str,
        emoji: str = None,
        image: str = None,
    ):
        await itx.response.defer(ephemeral=True)

        # ── บันทึก panel ลง DB ────────────────────────────────────────────
        panel_id = db.rr_create_panel(
            guild_id=itx.guild.id,
            channel_id=channel.id,
            title=label,
            description=f"กดปุ่มด้านล่างเพื่อรับ / ถอดยศ {role.mention}",
            image_url=image,
        )

        btn_id = db.rr_add_button(
            panel_id=panel_id,
            guild_id=itx.guild.id,
            role_id=role.id,
            label=label,
            emoji=emoji,
            sort_order=0,
        )

        # ── สร้าง Embed ───────────────────────────────────────────────────
        embed = discord.Embed(
            title=label,
            description=f"กดปุ่มด้านล่างเพื่อรับ / ถอดยศ {role.mention}",
            color=0x5865F2,
        )
        if image:
            embed.set_image(url=image)

        # ── สร้าง View ────────────────────────────────────────────────────
        view = discord.ui.View(timeout=None)
        view.add_item(RoleButton(
            panel_id=panel_id,
            btn_id=btn_id,
            role_id=role.id,
            label=label,
            emoji=emoji,
        ))
        self.bot.add_view(view)

        # ── ส่งไปห้องที่เลือก ─────────────────────────────────────────────
        try:
            msg = await channel.send(embed=embed, view=view)
        except discord.Forbidden:
            db.rr_delete_panel(panel_id)
            return await itx.followup.send(
                f"❌ บอทไม่มีสิทธิ์ส่งข้อความใน {channel.mention}\n"
                "กรุณาตรวจสอบสิทธิ์ของบอทในห้องนั้น",
                ephemeral=True,
            )

        db.rr_update_panel(panel_id, message_id=msg.id)

        # ── ตอบกลับ admin ──────────────────────────────────────────────────
        confirm = discord.Embed(
            title="✅ ส่งปุ่มรับยศเรียบร้อย!",
            color=0x57F287,
        )
        confirm.add_field(name="📢 ห้อง",    value=channel.mention, inline=True)
        confirm.add_field(name="🏅 ยศ",      value=role.mention,    inline=True)
        confirm.add_field(name="🏷️ ข้อความ", value=label,           inline=True)
        if emoji:
            confirm.add_field(name="😀 อิโมจิ", value=emoji,       inline=True)
        if image:
            confirm.add_field(name="🖼️ รูปภาพ", value="✅ แนบแล้ว", inline=True)
        confirm.set_footer(text="กดปุ่มอีกครั้ง = ถอดยศ (toggle) • ปุ่มใช้งานได้ถาวร")

        await itx.followup.send(embed=confirm, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SetRoleCog(bot))
                 
