"""
cogs/rolereact.py  –  ระบบรับยศแบบกดปุ่มอิสระ (/rolereact)

Admin ตั้งค่าผ่าน /rolereact:
  /rolereact create   — สร้าง panel ใหม่ (ตั้งชื่อ/คำอธิบาย/รูป/สี)
  /rolereact addbutton — เพิ่มปุ่มรับยศเข้า panel
  /rolereact removebutton — ลบปุ่มออกจาก panel
  /rolereact edit     — แก้ไข title/description/รูป/สีของ panel
  /rolereact send     — ส่ง panel ไปยังห้องที่เลือก
  /rolereact delete   — ลบ panel ทิ้ง
  /rolereact list     — ดู panel ทั้งหมดใน server

User กดปุ่มใน panel → ได้/หายยศ (toggle)
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils.database import Database

db = Database()

STYLE_MAP = {
    "grey":   discord.ButtonStyle.secondary,
    "blue":   discord.ButtonStyle.primary,
    "green":  discord.ButtonStyle.success,
    "red":    discord.ButtonStyle.danger,
}

COLOR_MAP = {
    "grey":   0x99AAB5,
    "blue":   0x5865F2,
    "green":  0x57F287,
    "red":    0xED4245,
    "gold":   0xFEE75C,
    "purple": 0x9B59B6,
    "orange": 0xE67E22,
    "white":  0xFFFFFF,
}


def _build_embed(panel: dict) -> discord.Embed:
    embed = discord.Embed(
        title=panel["title"],
        description=panel["description"],
        color=panel.get("color") or 0x5793266,
    )
    if panel.get("image_url"):
        embed.set_image(url=panel["image_url"])
    return embed


def _build_view(panel_id: int, guild: discord.Guild) -> discord.ui.View:
    """สร้าง View จาก buttons ใน DB"""
    view = discord.ui.View(timeout=None)
    buttons = db.rr_get_buttons(panel_id)
    for btn in buttons:
        style = STYLE_MAP.get(btn.get("style", "grey"), discord.ButtonStyle.secondary)
        emoji_val = btn.get("emoji") or None
        b = RoleReactButton(
            panel_id=panel_id,
            role_id=btn["role_id"],
            label=btn["label"],
            emoji=emoji_val,
            style=style,
            btn_id=btn["id"],
        )
        view.add_item(b)
    return view


class RoleReactButton(discord.ui.Button):
    def __init__(self, panel_id: int, role_id: int, label: str,
                 emoji: str | None, style: discord.ButtonStyle, btn_id: int):
        self.panel_id = panel_id
        self.role_id  = role_id
        super().__init__(
            label=label,
            emoji=emoji,
            style=style,
            custom_id=f"rr:{panel_id}:{btn_id}:{role_id}",
        )

    async def callback(self, itx: discord.Interaction):
        guild = itx.guild
        user  = itx.user

        role = guild.get_role(self.role_id)
        if not role:
            return await itx.response.send_message(
                "❌ ไม่พบยศนี้ในเซิร์ฟเวอร์ กรุณาแจ้งแอดมิน", ephemeral=True
            )

        if role in user.roles:
            await user.remove_roles(role, reason="rolereact self-remove")
            await itx.response.send_message(
                f"➖ เอายศ **{role.name}** ออกแล้ว", ephemeral=True
            )
        else:
            await user.add_roles(role, reason="rolereact self-assign")
            await itx.response.send_message(
                f"✅ ได้รับยศ **{role.name}** แล้ว!", ephemeral=True
            )


# ════════════════════════════════════════════════════════════════════════════
#  Cog
# ════════════════════════════════════════════════════════════════════════════

class RoleReactCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """Re-register persistent views สำหรับทุก panel หลัง bot restart"""
        # ดึง panel ทุกอันจาก DB แล้ว register view
        # (ทำโดยใช้ raw SQL เพราะไม่มี list all panels across guilds)
        with db.conn() as conn:
            rows = conn.execute(
                "SELECT * FROM rr_panels WHERE message_id IS NOT NULL"
            ).fetchall()
        for row in rows:
            panel = dict(row)
            # สร้าง view แบบ minimal เพื่อ register custom_id เท่านั้น
            # (guild object ยังไม่พร้อม ณ จุดนี้ แต่ custom_id ลงทะเบียนได้)
            buttons = db.rr_get_buttons(panel["id"])
            view = discord.ui.View(timeout=None)
            for btn in buttons:
                style = STYLE_MAP.get(btn.get("style", "grey"), discord.ButtonStyle.secondary)
                b = RoleReactButton(
                    panel_id=panel["id"],
                    role_id=btn["role_id"],
                    label=btn["label"],
                    emoji=btn.get("emoji"),
                    style=style,
                    btn_id=btn["id"],
                )
                view.add_item(b)
            self.bot.add_view(view)

    # ── Group ─────────────────────────────────────────────────────────────
    rolereact = app_commands.Group(
        name="rolereact",
        description="🎭 ระบบรับยศแบบกดปุ่มอิสระ",
        default_permissions=discord.Permissions(administrator=True),
    )

    # ── /rolereact create ─────────────────────────────────────────────────
    @rolereact.command(name="create", description="➕ สร้าง Panel รับยศใหม่")
    @app_commands.describe(
        title="หัวข้อ Panel",
        description="คำอธิบายใต้หัวข้อ",
        color="สี embed: blue / green / red / gold / purple / orange / grey / white",
        image_url="URL รูปภาพ (ถ้าต้องการ)",
    )
    @app_commands.choices(color=[
        app_commands.Choice(name="🔵 Blue",   value="blue"),
        app_commands.Choice(name="🟢 Green",  value="green"),
        app_commands.Choice(name="🔴 Red",    value="red"),
        app_commands.Choice(name="🟡 Gold",   value="gold"),
        app_commands.Choice(name="🟣 Purple", value="purple"),
        app_commands.Choice(name="🟠 Orange", value="orange"),
        app_commands.Choice(name="⚫ Grey",   value="grey"),
        app_commands.Choice(name="⚪ White",  value="white"),
    ])
    async def cmd_create(
        self,
        itx: discord.Interaction,
        title: str,
        description: str,
        color: str = "blue",
        image_url: str = None,
    ):
        color_int = COLOR_MAP.get(color, 0x5865F2)
        panel_id = db.rr_create_panel(
            guild_id=itx.guild.id,
            channel_id=itx.channel.id,
            title=title,
            description=description,
            image_url=image_url,
            color=color_int,
        )
        embed = discord.Embed(
            title="✅ สร้าง Panel สำเร็จ!",
            description=(
                f"**ID:** `{panel_id}`\n"
                f"**ชื่อ:** {title}\n\n"
                "ขั้นตอนถัดไป:\n"
                f"1️⃣ `/rolereact addbutton panel_id:{panel_id}` — เพิ่มปุ่มรับยศ\n"
                f"2️⃣ `/rolereact send panel_id:{panel_id}` — ส่ง Panel ไปยังห้อง"
            ),
            color=color_int,
        )
        await itx.response.send_message(embed=embed, ephemeral=True)

    # ── /rolereact addbutton ──────────────────────────────────────────────
    @rolereact.command(name="addbutton", description="🔘 เพิ่มปุ่มรับยศเข้า Panel")
    @app_commands.describe(
        panel_id="ID ของ Panel (ดูได้จาก /rolereact list)",
        role="Role ที่จะให้เมื่อกดปุ่มนี้",
        label="ข้อความบนปุ่ม",
        emoji="อิโมจิบนปุ่ม (ไม่บังคับ) เช่น 🎮",
        style="สีปุ่ม",
    )
    @app_commands.choices(style=[
        app_commands.Choice(name="⚫ Grey (default)", value="grey"),
        app_commands.Choice(name="🔵 Blue",           value="blue"),
        app_commands.Choice(name="🟢 Green",          value="green"),
        app_commands.Choice(name="🔴 Red",            value="red"),
    ])
    async def cmd_addbutton(
        self,
        itx: discord.Interaction,
        panel_id: int,
        role: discord.Role,
        label: str,
        emoji: str = None,
        style: str = "grey",
    ):
        panel = db.rr_get_panel(panel_id)
        if not panel or panel["guild_id"] != itx.guild.id:
            return await itx.response.send_message("❌ ไม่พบ Panel นี้", ephemeral=True)

        # จำกัด 25 ปุ่ม (Discord limit)
        current = db.rr_get_buttons(panel_id)
        if len(current) >= 25:
            return await itx.response.send_message(
                "❌ Panel นี้มีปุ่มครบ 25 อันแล้ว (Discord limit)", ephemeral=True
            )

        sort_order = len(current)
        btn_id = db.rr_add_button(
            panel_id=panel_id,
            guild_id=itx.guild.id,
            role_id=role.id,
            label=label,
            emoji=emoji,
            style=style,
            sort_order=sort_order,
        )

        await itx.response.send_message(
            f"✅ เพิ่มปุ่ม **{label}** → {role.mention} เข้า Panel `{panel_id}` แล้ว\n"
            f"(Button ID: `{btn_id}`)\n\n"
            f"ถ้า Panel ส่งไปแล้ว ใช้ `/rolereact refresh panel_id:{panel_id}` เพื่ออัพเดต",
            ephemeral=True,
        )

    # ── /rolereact removebutton ───────────────────────────────────────────
    @rolereact.command(name="removebutton", description="🗑️ ลบปุ่มออกจาก Panel")
    @app_commands.describe(
        panel_id="ID ของ Panel",
        role="Role ที่ต้องการลบปุ่มออก",
    )
    async def cmd_removebutton(
        self,
        itx: discord.Interaction,
        panel_id: int,
        role: discord.Role,
    ):
        panel = db.rr_get_panel(panel_id)
        if not panel or panel["guild_id"] != itx.guild.id:
            return await itx.response.send_message("❌ ไม่พบ Panel นี้", ephemeral=True)

        btn = db.rr_get_button_by_role(panel_id, role.id)
        if not btn:
            return await itx.response.send_message(
                f"❌ ไม่พบปุ่มสำหรับ {role.mention} ใน Panel นี้", ephemeral=True
            )

        db.rr_remove_button(btn["id"])
        await itx.response.send_message(
            f"✅ ลบปุ่ม **{btn['label']}** ({role.mention}) ออกแล้ว\n"
            f"ใช้ `/rolereact refresh panel_id:{panel_id}` เพื่ออัพเดต",
            ephemeral=True,
        )

    # ── /rolereact edit ───────────────────────────────────────────────────
    @rolereact.command(name="edit", description="✏️ แก้ไข Panel (ชื่อ/คำอธิบาย/รูป/สี)")
    @app_commands.describe(
        panel_id="ID ของ Panel",
        title="หัวข้อใหม่ (เว้นว่างเพื่อคงเดิม)",
        description="คำอธิบายใหม่ (เว้นว่างเพื่อคงเดิม)",
        color="สีใหม่",
        image_url="URL รูปใหม่ (พิมพ์ 'clear' เพื่อลบรูป)",
    )
    @app_commands.choices(color=[
        app_commands.Choice(name="🔵 Blue",   value="blue"),
        app_commands.Choice(name="🟢 Green",  value="green"),
        app_commands.Choice(name="🔴 Red",    value="red"),
        app_commands.Choice(name="🟡 Gold",   value="gold"),
        app_commands.Choice(name="🟣 Purple", value="purple"),
        app_commands.Choice(name="🟠 Orange", value="orange"),
        app_commands.Choice(name="⚫ Grey",   value="grey"),
        app_commands.Choice(name="⚪ White",  value="white"),
    ])
    async def cmd_edit(
        self,
        itx: discord.Interaction,
        panel_id: int,
        title: str = None,
        description: str = None,
        color: str = None,
        image_url: str = None,
    ):
        panel = db.rr_get_panel(panel_id)
        if not panel or panel["guild_id"] != itx.guild.id:
            return await itx.response.send_message("❌ ไม่พบ Panel นี้", ephemeral=True)

        updates = {}
        if title:
            updates["title"] = title
        if description:
            updates["description"] = description
        if color:
            updates["color"] = COLOR_MAP.get(color, panel["color"])
        if image_url:
            updates["image_url"] = None if image_url.lower() == "clear" else image_url

        if not updates:
            return await itx.response.send_message("⚠️ ไม่มีอะไรเปลี่ยน", ephemeral=True)

        db.rr_update_panel(panel_id, **updates)
        await itx.response.send_message(
            f"✅ อัพเดต Panel `{panel_id}` แล้ว\n"
            f"ใช้ `/rolereact refresh panel_id:{panel_id}` เพื่ออัพเดตข้อความใน Discord",
            ephemeral=True,
        )

    # ── /rolereact send ───────────────────────────────────────────────────
    @rolereact.command(name="send", description="📨 ส่ง Panel ไปยังห้องที่เลือก")
    @app_commands.describe(
        panel_id="ID ของ Panel",
        channel="ห้องที่จะส่ง Panel ไป (เว้นว่าง = ห้องปัจจุบัน)",
    )
    async def cmd_send(
        self,
        itx: discord.Interaction,
        panel_id: int,
        channel: discord.TextChannel = None,
    ):
        panel = db.rr_get_panel(panel_id)
        if not panel or panel["guild_id"] != itx.guild.id:
            return await itx.response.send_message("❌ ไม่พบ Panel นี้", ephemeral=True)

        buttons = db.rr_get_buttons(panel_id)
        if not buttons:
            return await itx.response.send_message(
                "❌ Panel นี้ยังไม่มีปุ่ม ใช้ `/rolereact addbutton` ก่อน", ephemeral=True
            )

        target = channel or itx.channel
        embed  = _build_embed(panel)
        view   = _build_view(panel_id, itx.guild)

        # Register view กับ bot (persistent)
        self.bot.add_view(view)

        msg = await target.send(embed=embed, view=view)
        db.rr_update_panel(panel_id, message_id=msg.id, channel_id=target.id)

        await itx.response.send_message(
            f"✅ ส่ง Panel ไปที่ {target.mention} แล้ว!", ephemeral=True
        )

    # ── /rolereact refresh ────────────────────────────────────────────────
    @rolereact.command(name="refresh", description="🔄 อัพเดต Panel ที่ส่งไปแล้ว")
    @app_commands.describe(panel_id="ID ของ Panel ที่ต้องการอัพเดต")
    async def cmd_refresh(self, itx: discord.Interaction, panel_id: int):
        panel = db.rr_get_panel(panel_id)
        if not panel or panel["guild_id"] != itx.guild.id:
            return await itx.response.send_message("❌ ไม่พบ Panel นี้", ephemeral=True)
        if not panel.get("message_id"):
            return await itx.response.send_message(
                "❌ Panel นี้ยังไม่ได้ส่ง ใช้ `/rolereact send` ก่อน", ephemeral=True
            )

        ch = itx.guild.get_channel(panel["channel_id"])
        if not ch:
            return await itx.response.send_message("❌ ไม่พบห้องที่ส่ง Panel ไป", ephemeral=True)

        try:
            msg = await ch.fetch_message(panel["message_id"])
        except discord.NotFound:
            return await itx.response.send_message(
                "❌ ไม่พบข้อความ Panel (อาจถูกลบไปแล้ว)", ephemeral=True
            )

        embed = _build_embed(panel)
        view  = _build_view(panel_id, itx.guild)
        self.bot.add_view(view)

        await msg.edit(embed=embed, view=view)
        await itx.response.send_message("✅ อัพเดต Panel เรียบร้อย!", ephemeral=True)

    # ── /rolereact delete ─────────────────────────────────────────────────
    @rolereact.command(name="delete", description="🗑️ ลบ Panel ทิ้ง (ลบข้อความใน Discord ด้วย)")
    @app_commands.describe(panel_id="ID ของ Panel ที่ต้องการลบ")
    async def cmd_delete(self, itx: discord.Interaction, panel_id: int):
        panel = db.rr_get_panel(panel_id)
        if not panel or panel["guild_id"] != itx.guild.id:
            return await itx.response.send_message("❌ ไม่พบ Panel นี้", ephemeral=True)

        # ลบข้อความใน Discord ด้วยถ้ามี
        if panel.get("message_id") and panel.get("channel_id"):
            ch = itx.guild.get_channel(panel["channel_id"])
            if ch:
                try:
                    msg = await ch.fetch_message(panel["message_id"])
                    await msg.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass

        db.rr_delete_panel(panel_id)
        await itx.response.send_message(
            f"✅ ลบ Panel `{panel_id}` เรียบร้อยแล้ว", ephemeral=True
        )

    # ── /rolereact list ───────────────────────────────────────────────────
    @rolereact.command(name="list", description="📋 ดู Panel ทั้งหมดใน Server")
    async def cmd_list(self, itx: discord.Interaction):
        panels = db.rr_list_panels(itx.guild.id)
        if not panels:
            return await itx.response.send_message(
                "ยังไม่มี Panel ใช้ `/rolereact create` เพื่อสร้าง", ephemeral=True
            )

        embed = discord.Embed(
            title="📋 RoleReact Panels",
            color=discord.Color.blurple(),
        )

        for panel in panels:
            buttons  = db.rr_get_buttons(panel["id"])
            ch       = itx.guild.get_channel(panel["channel_id"])
            status   = "📨 ส่งแล้ว" if panel.get("message_id") else "📝 ยังไม่ส่ง"
            btn_list = ", ".join(
                f"{b['emoji'] or ''}{b['label']}"
                for b in buttons
            ) or "ยังไม่มีปุ่ม"

            embed.add_field(
                name=f"ID `{panel['id']}` — {panel['title']} {status}",
                value=(
                    f"ห้อง: {ch.mention if ch else '?'}\n"
                    f"ปุ่ม ({len(buttons)}): {btn_list}"
                ),
                inline=False,
            )

        embed.set_footer(text="ใช้ /rolereact send panel_id:<id> เพื่อส่ง Panel")
        await itx.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleReactCog(bot))
  
