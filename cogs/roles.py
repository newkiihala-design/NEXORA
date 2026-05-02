"""
cogs/roles.py  –  ระบบรับยศแบบ Flow (/setrole)

ผู้ใช้กด panel → เลือกจุดประสงค์ → ถ้าเลือกซื้อของ/ทั้งสองอย่าง จะขึ้น submenu ประเภทซื้อขาย

Admin ตั้งค่าผ่าน /setrole:
  /setrole panel              — ส่ง panel ไปห้องปัจจุบัน
  /setrole setoption          — กำหนด Role ให้ตัวเลือก
  /setrole list               — ดูรายการตัวเลือกทั้งหมด
"""

import discord
from discord import app_commands
from discord.ext import commands

from utils.database import Database

db = Database()

# ── กลุ่มและตัวเลือกที่ built-in (structure คงที่ตามคอนเซ็ปต์) ──────────────
GROUPS = {
    "purpose": {
        "label": "🎯 เลือกจุดประสงค์ของคุณ",
        "desc":  "คุณเข้า Server นี้เพื่ออะไร?",
    },
    "trade": {
        "label": "🛒 เลือกประเภทสินค้าที่สนใจ",
        "desc":  "คุณต้องการซื้อขายสินค้าประเภทไหน?",
    },
}

# option_key → (group, label, has_submenu)
OPTIONS = {
    "purpose": [
        ("find_friend", "👥 หาเพื่อน",       False),
        ("buy",         "🛒 ซื้อของ",         True),   # → submenu trade
        ("both",        "✨ ทั้งสองอย่าง",    True),   # → submenu trade ด้วย
    ],
    "trade": [
        ("topup",   "🎮 เติมเกม & เติมแอพ",  False),
        ("script",  "💻 ซื้อขายสคริปต์",     False),
        ("all",     "🌟 ทั้งหมด",             False),
    ],
}

# ตัวเลือก purpose ที่ trigger submenu trade
TRADE_TRIGGERS = {"buy", "both"}


def _get_role(guild: discord.Guild, group: str, option: str) -> discord.Role | None:
    opts = db.get_role_options(guild.id, group)
    for o in opts:
        if o["option_key"] == option and o["role_id"]:
            return guild.get_role(o["role_id"])
    return None


def _ensure_options(guild_id: int):
    """Seed ตัวเลือกเริ่มต้นถ้ายังไม่มีใน DB (ไม่ overwrite role_id ที่ตั้งแล้ว)"""
    for gkey, opts in OPTIONS.items():
        existing = {o["option_key"] for o in db.get_role_options(guild_id, gkey)}
        for i, (okey, label, has_sub) in enumerate(opts):
            if okey not in existing:
                db.upsert_role_option(
                    guild_id, gkey, okey, label,
                    has_submenu=has_sub, sort_order=i
                )


# ════════════════════════════════════════════════════════════════════════════
#  Views
# ════════════════════════════════════════════════════════════════════════════

class PurposeView(discord.ui.View):
    """Panel หลัก: เลือกจุดประสงค์"""

    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=None)
        self.guild = guild
        _ensure_options(guild.id)

        opts = db.get_role_options(guild.id, "purpose")
        for opt in opts:
            self.add_item(PurposeButton(opt))


class PurposeButton(discord.ui.Button):
    def __init__(self, opt: dict):
        self.opt_data = opt
        has_sub = bool(opt.get("has_submenu"))
        super().__init__(
            label=opt["label"],
            style=discord.ButtonStyle.primary if has_sub else discord.ButtonStyle.secondary,
            custom_id=f"srole:purpose:{opt['option_key']}",
        )

    async def callback(self, itx: discord.Interaction):
        opt   = self.opt_data
        guild = itx.guild
        user  = itx.user

        lines: list[str] = []

        # ให้/เอา role ของ purpose นี้
        role = _get_role(guild, "purpose", opt["option_key"])
        if role:
            if role in user.roles:
                await user.remove_roles(role, reason="setrole self-remove")
                lines.append(f"➖ เอายศ **{role.name}** ออกแล้ว")
            else:
                await user.add_roles(role, reason="setrole self-assign")
                lines.append(f"✅ ได้รับยศ **{role.name}** แล้ว")
        else:
            lines.append(f"✅ เลือก **{opt['label']}** แล้ว")

        # ถ้า option นี้ trigger submenu trade → แสดง submenu ต่อ
        if opt["option_key"] in TRADE_TRIGGERS:
            embed = discord.Embed(
                title=GROUPS["trade"]["label"],
                description=GROUPS["trade"]["desc"],
                color=discord.Color.gold(),
            )
            _add_role_fields(embed, guild, "trade")
            await itx.response.send_message(
                content="\n".join(lines) if lines else None,
                embed=embed,
                view=TradeView(guild),
                ephemeral=True,
            )
        else:
            await itx.response.send_message(
                "\n".join(lines) or "✅ เสร็จสิ้น",
                ephemeral=True,
            )


class TradeView(discord.ui.View):
    """Submenu: เลือกประเภทซื้อขาย"""

    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=60)
        opts = db.get_role_options(guild.id, "trade")
        for opt in opts:
            self.add_item(TradeButton(opt))


class TradeButton(discord.ui.Button):
    def __init__(self, opt: dict):
        self.opt_data = opt
        super().__init__(
            label=opt["label"],
            style=discord.ButtonStyle.secondary,
            custom_id=f"srole:trade:{opt['option_key']}:{opt['id']}",
        )

    async def callback(self, itx: discord.Interaction):
        opt   = self.opt_data
        guild = itx.guild
        user  = itx.user

        role = _get_role(guild, "trade", opt["option_key"])
        if not role:
            return await itx.response.send_message(
                "⚠️ ตัวเลือกนี้ยังไม่ได้กำหนดยศ กรุณาแจ้งแอดมิน", ephemeral=True
            )

        if role in user.roles:
            await user.remove_roles(role, reason="setrole trade self-remove")
            msg = f"➖ เอายศ **{role.name}** ออกแล้ว"
        else:
            await user.add_roles(role, reason="setrole trade self-assign")
            msg = f"✅ ได้รับยศ **{role.name}** แล้ว"

        await itx.response.send_message(msg, ephemeral=True)


def _add_role_fields(embed: discord.Embed, guild: discord.Guild, group: str):
    """เพิ่ม field แสดง role ที่ตั้งค่าแต่ละตัวเลือก"""
    opts = db.get_role_options(guild.id, group)
    for opt in opts:
        role = guild.get_role(opt["role_id"]) if opt["role_id"] else None
        embed.add_field(
            name=opt["label"],
            value=role.mention if role else "`ยังไม่ได้กำหนดยศ`",
            inline=True,
        )


# ════════════════════════════════════════════════════════════════════════════
#  Cog
# ════════════════════════════════════════════════════════════════════════════

class RolesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    setrole = app_commands.Group(
        name="setrole",
        description="⚙️ ระบบรับยศแบบ Flow",
        default_permissions=discord.Permissions(administrator=True),
    )

    # ── /setrole panel ────────────────────────────────────────────────────
    @setrole.command(name="panel", description="📨 ส่ง Panel รับยศไปยังห้องปัจจุบัน")
    async def cmd_panel(self, itx: discord.Interaction):
        guild = itx.guild
        _ensure_options(guild.id)

        embed = discord.Embed(
            title=GROUPS["purpose"]["label"],
            description=(
                f"{GROUPS['purpose']['desc']}\n\n"
                "กดปุ่มเพื่อรับยศ — กดซ้ำเพื่อเอายศออก\n"
                "หากเลือก **ซื้อของ** หรือ **ทั้งสองอย่าง** จะมีเมนูเพิ่มเติม"
            ),
            color=discord.Color.blurple(),
        )
        _add_role_fields(embed, guild, "purpose")
        embed.set_footer(text="กดปุ่มด้านล่างเพื่อเลือก")

        await itx.channel.send(embed=embed, view=PurposeView(guild))
        await itx.response.send_message("✅ ส่ง Panel รับยศแล้ว!", ephemeral=True)

    # ── /setrole setoption ────────────────────────────────────────────────
    @setrole.command(name="setoption", description="🎭 กำหนด Role ให้ตัวเลือก")
    @app_commands.describe(
        group="กลุ่ม: purpose หรือ trade",
        option="ชื่อตัวเลือก เช่น find_friend, buy, both, topup, script, all",
        role="Role ที่จะให้เมื่อกดตัวเลือกนี้",
    )
    @app_commands.choices(group=[
        app_commands.Choice(name="🎯 จุดประสงค์ (purpose)", value="purpose"),
        app_commands.Choice(name="🛒 ประเภทซื้อขาย (trade)",  value="trade"),
    ])
    async def cmd_setoption(
        self,
        itx: discord.Interaction,
        group: str,
        option: str,
        role: discord.Role,
    ):
        _ensure_options(itx.guild.id)
        valid = {o[0] for o in OPTIONS.get(group, [])}
        if option not in valid:
            opts_str = ", ".join(f"`{o}`" for o in valid)
            return await itx.response.send_message(
                f"❌ ตัวเลือกไม่ถูกต้อง\nตัวเลือกที่มีใน **{group}**: {opts_str}",
                ephemeral=True,
            )

        # หา label จาก built-in
        label = next((lb for k, lb, _ in OPTIONS[group] if k == option), option)
        db.upsert_role_option(itx.guild.id, group, option, label, role_id=role.id)

        await itx.response.send_message(
            f"✅ กำหนด {role.mention} → **{label}** (`{group}/{option}`) เรียบร้อยแล้ว",
            ephemeral=True,
        )

    # ── /setrole list ─────────────────────────────────────────────────────
    @setrole.command(name="list", description="📋 ดูรายการตัวเลือกและ Role ที่กำหนดไว้")
    async def cmd_list(self, itx: discord.Interaction):
        guild = itx.guild
        _ensure_options(guild.id)

        embed = discord.Embed(
            title="📋 รายการ Role System (Flow)",
            color=discord.Color.blurple(),
        )

        for gkey, gdata in GROUPS.items():
            opts = db.get_role_options(guild.id, gkey)
            lines = []
            for opt in opts:
                role = guild.get_role(opt["role_id"]) if opt["role_id"] else None
                sub  = " `→ submenu`" if opt.get("has_submenu") else ""
                lines.append(
                    f"• `{opt['option_key']}` {opt['label']}{sub} — "
                    + (role.mention if role else "⚠️ ยังไม่กำหนด")
                )
            embed.add_field(
                name=gdata["label"],
                value="\n".join(lines) or "ไม่มีตัวเลือก",
                inline=False,
            )

        embed.set_footer(text="ใช้ /setrole setoption เพื่อกำหนด Role")
        await itx.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(RolesCog(bot))
