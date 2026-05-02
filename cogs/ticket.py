"""
cogs/ticket.py  –  ระบบ Ticket หลัก
ฟีเจอร์: สร้าง/ปิด Ticket, หมวดหมู่, Assign, Cooldown,
         Transcript HTML, Rating, Priority, /add /remove
"""

import asyncio
import io
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from utils.database import Database
from utils.transcript import generate_html

db = Database()

# ── ค่าคงที่ ────────────────────────────────────────────────────────────────
CATS = {
    "problem": {
        "label":  "🔴 แจ้งปัญหา",
        "emoji":  "🔴",
        "color":  discord.Color.from_rgb(240, 71, 71),
        "desc":   "สำหรับแจ้งปัญหาเกี่ยวกับระบบหรือบริการ",
    },
    "payment": {
        "label":  "💰 เติมเงิน / ชำระเงิน",
        "emoji":  "💰",
        "color":  discord.Color.from_rgb(35, 165, 90),
        "desc":   "สำหรับการเติมเงิน ตรวจสอบยอด หรือปัญหาการชำระเงิน",
    },
    "general": {
        "label":  "💬 สอบถามทั่วไป",
        "emoji":  "💬",
        "color":  discord.Color.from_rgb(88, 101, 242),
        "desc":   "สำหรับคำถามทั่วไปและข้อสงสัยต่างๆ",
    },
    "vip": {
        "label":  "⭐ VIP Support",
        "emoji":  "⭐",
        "color":  discord.Color.from_rgb(240, 178, 50),
        "desc":   "ช่องทางพิเศษสำหรับสมาชิก VIP",
    },
}

PRIORITY_MAP = {
    "high":   "🔴 สูง",
    "normal": "🟡 ปกติ",
    "low":    "🟢 ต่ำ",
}


# ════════════════════════════════════════════════════════════════════════════
#  UI  Views
# ════════════════════════════════════════════════════════════════════════════

class CategorySelectView(discord.ui.View):
    """Panel ปุ่มเลือกหมวดหมู่ Ticket"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🔴 แจ้งปัญหา", style=discord.ButtonStyle.danger,
        custom_id="ticket:problem", row=0
    )
    async def btn_problem(self, itx: discord.Interaction, _):
        await _open_ticket(itx, "problem")

    @discord.ui.button(
        label="💰 เติมเงิน", style=discord.ButtonStyle.success,
        custom_id="ticket:payment", row=0
    )
    async def btn_payment(self, itx: discord.Interaction, _):
        await _open_ticket(itx, "payment")

    @discord.ui.button(
        label="💬 สอบถาม", style=discord.ButtonStyle.primary,
        custom_id="ticket:general", row=0
    )
    async def btn_general(self, itx: discord.Interaction, _):
        await _open_ticket(itx, "general")

    @discord.ui.button(
        label="⭐ VIP", style=discord.ButtonStyle.secondary,
        custom_id="ticket:vip", row=0
    )
    async def btn_vip(self, itx: discord.Interaction, _):
        cfg = db.get_config(itx.guild.id)
        # ตรวจสอบ vip_role ถ้ามีการตั้งค่าไว้
        if cfg and cfg.get("vip_role_id"):
            vip_role = itx.guild.get_role(cfg["vip_role_id"])
            if vip_role and vip_role not in itx.user.roles:
                return await itx.response.send_message(
                    f"❌ ช่องทางนี้สำหรับสมาชิก {vip_role.mention} เท่านั้น",
                    ephemeral=True,
                )
        await _open_ticket(itx, "vip", priority="high")


class TicketControlView(discord.ui.View):
    """ปุ่มควบคุมภายใน Ticket channel"""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🔒 ปิด Ticket", style=discord.ButtonStyle.danger,
        custom_id="ticket:close", row=0
    )
    async def btn_close(self, itx: discord.Interaction, _):
        ticket = db.get_ticket(itx.channel.id)
        if not ticket:
            return await itx.response.send_message("❌ ห้องนี้ไม่ใช่ Ticket", ephemeral=True)

        if not _can_manage(itx, ticket):
            return await itx.response.send_message(
                "❌ เฉพาะเจ้าของหรือแอดมินเท่านั้น", ephemeral=True
            )

        view = ConfirmCloseView(ticket)
        embed = discord.Embed(
            description="⚠️ **คุณแน่ใจว่าต้องการปิด Ticket นี้?**\nระบบจะบันทึก Transcript และลบห้องนี้",
            color=discord.Color.orange(),
        )
        await itx.response.send_message(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(
        label="👤 รับเคส", style=discord.ButtonStyle.success,
        custom_id="ticket:assign", row=0
    )
    async def btn_assign(self, itx: discord.Interaction, _):
        ticket = db.get_ticket(itx.channel.id)
        if not ticket:
            return await itx.response.send_message("❌ ห้องนี้ไม่ใช่ Ticket", ephemeral=True)
        if not _is_staff(itx):
            return await itx.response.send_message("❌ เฉพาะ Staff เท่านั้น", ephemeral=True)

        db.assign_ticket(itx.channel.id, itx.user.id)
        embed = discord.Embed(
            description=f"✅ **{itx.user.display_name}** รับเคสนี้แล้ว",
            color=discord.Color.green(),
        )
        await itx.response.send_message(embed=embed)

    @discord.ui.button(
        label="📋 Transcript", style=discord.ButtonStyle.secondary,
        custom_id="ticket:transcript", row=0
    )
    async def btn_transcript(self, itx: discord.Interaction, _):
        if not _is_staff(itx):
            return await itx.response.send_message("❌ เฉพาะ Staff เท่านั้น", ephemeral=True)

        ticket = db.get_ticket(itx.channel.id)
        if not ticket:
            return await itx.response.send_message("❌ ไม่พบข้อมูล Ticket", ephemeral=True)

        await itx.response.defer(ephemeral=True)
        html = await generate_html(itx.channel, ticket)
        file = discord.File(
            io.BytesIO(html.encode()), filename=f"{itx.channel.name}-transcript.html"
        )
        await itx.followup.send("📋 นี่คือ Transcript ของ Ticket นี้:", file=file, ephemeral=True)


class ConfirmCloseView(discord.ui.View):
    def __init__(self, ticket: dict):
        super().__init__(timeout=30)
        self.ticket = ticket

    @discord.ui.button(label="✅ ยืนยัน ปิด Ticket", style=discord.ButtonStyle.danger)
    async def confirm(self, itx: discord.Interaction, _):
        self.stop()
        await itx.response.defer()
        await _close_ticket(itx.channel, itx.user, self.ticket)

    @discord.ui.button(label="❌ ยกเลิก", style=discord.ButtonStyle.secondary)
    async def cancel(self, itx: discord.Interaction, _):
        self.stop()
        await itx.response.send_message("✅ ยกเลิกการปิด Ticket แล้ว", ephemeral=True)


class RatingView(discord.ui.View):
    """ส่ง DM ให้ผู้ใช้ Rating หลังปิด Ticket"""

    STARS = ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]

    def __init__(self, channel_id: int, user_id: int):
        super().__init__(timeout=300)
        self.channel_id = channel_id
        self.user_id    = user_id

    async def _rate(self, itx: discord.Interaction, score: int):
        if itx.user.id != self.user_id:
            return await itx.response.send_message("❌ ไม่ใช่ Ticket ของคุณ", ephemeral=True)
        db.rate_ticket(self.channel_id, score)
        stars = self.STARS[score - 1]
        self.stop()
        await itx.response.edit_message(
            content=f"✅ ขอบคุณสำหรับคะแนน! {stars} ({score}/5)\nเราจะปรับปรุงการบริการให้ดียิ่งขึ้น",
            view=None,
        )

    @discord.ui.button(label="1 ⭐", style=discord.ButtonStyle.secondary)
    async def r1(self, i, _): await self._rate(i, 1)
    @discord.ui.button(label="2 ⭐", style=discord.ButtonStyle.secondary)
    async def r2(self, i, _): await self._rate(i, 2)
    @discord.ui.button(label="3 ⭐", style=discord.ButtonStyle.primary)
    async def r3(self, i, _): await self._rate(i, 3)
    @discord.ui.button(label="4 ⭐", style=discord.ButtonStyle.primary)
    async def r4(self, i, _): await self._rate(i, 4)
    @discord.ui.button(label="5 ⭐", style=discord.ButtonStyle.success)
    async def r5(self, i, _): await self._rate(i, 5)


# ════════════════════════════════════════════════════════════════════════════
#  Helper functions
# ════════════════════════════════════════════════════════════════════════════

def _is_staff(itx: discord.Interaction) -> bool:
    if itx.user.guild_permissions.administrator:
        return True
    cfg = db.get_config(itx.guild.id)
    if cfg:
        for rid in (cfg.get("admin_role_id"), cfg.get("support_role_id")):
            if rid:
                role = itx.guild.get_role(rid)
                if role and role in itx.user.roles:
                    return True
    return False


def _can_manage(itx: discord.Interaction, ticket: dict) -> bool:
    return ticket["user_id"] == itx.user.id or _is_staff(itx)


async def _open_ticket(
    itx: discord.Interaction,
    category: str,
    priority: str = "normal",
):
    guild = itx.guild
    user  = itx.user
    cfg   = db.get_config(guild.id)

    # ─ Cooldown ─────────────────────────────────────────────────────────────
    secs = cfg.get("cooldown_seconds", 300) if cfg else 300
    rem  = db.check_cooldown(user.id, guild.id, secs)
    if rem > 0:
        m, s = divmod(int(rem), 60)
        return await itx.response.send_message(
            f"⏱️ กรุณารอ **{m}:{s:02d}** ก่อนเปิด Ticket ใหม่", ephemeral=True
        )

    # ─ ตรวจสอบ Ticket ที่เปิดอยู่ ──────────────────────────────────────────
    existing = db.get_user_open_ticket(guild.id, user.id)
    if existing:
        ch = guild.get_channel(existing["channel_id"])
        mention = ch.mention if ch else f"ID:{existing['channel_id']}"
        return await itx.response.send_message(
            f"❌ คุณมี Ticket ที่เปิดอยู่แล้วที่ {mention}\nกรุณาปิด Ticket เดิมก่อน",
            ephemeral=True,
        )

    await itx.response.defer(ephemeral=True)

    # ─ Category channel ─────────────────────────────────────────────────────
    cat_ch = None
    if cfg and cfg.get("ticket_category_id"):
        cat_ch = guild.get_channel(cfg["ticket_category_id"])
    if not cat_ch:
        cat_ch = await guild.create_category("🎫 Tickets")
        db.set_config(guild.id, ticket_category_id=cat_ch.id)

    # ─ Permissions ──────────────────────────────────────────────────────────
    perms: dict = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user:               discord.PermissionOverwrite(
            view_channel=True, send_messages=True, read_message_history=True
        ),
        guild.me:           discord.PermissionOverwrite(
            view_channel=True, send_messages=True, manage_channels=True
        ),
    }
    if cfg:
        for rid in (cfg.get("admin_role_id"), cfg.get("support_role_id")):
            if rid:
                role = guild.get_role(rid)
                if role:
                    perms[role] = discord.PermissionOverwrite(
                        view_channel=True, send_messages=True, manage_channels=True
                    )

    # ─ สร้าง channel ────────────────────────────────────────────────────────
    num    = db.get_ticket_count(guild.id) + 1
    tid    = f"ticket-{num:04d}"
    cat    = CATS[category]
    ch_name = f"{cat['emoji']}-{user.name[:16]}-{num:04d}".lower().replace(" ", "-")

    channel = await guild.create_text_channel(
        name=ch_name,
        category=cat_ch,
        overwrites=perms,
        topic=f"Ticket #{num:04d} | {user.name} | {cat['label']}",
    )

    db.create_ticket(tid, guild.id, channel.id, user.id, category, priority)
    db.set_cooldown(user.id, guild.id)

    # ─ Welcome embed ─────────────────────────────────────────────────────────
    embed = discord.Embed(
        title=f"🎫 Ticket #{num:04d}",
        description=(
            f"ยินดีต้อนรับ {user.mention}!\n"
            f"ทีมงานจะเข้ามาช่วยเหลือคุณในเร็วๆ นี้\n"
            f"**กรุณาอธิบายปัญหาของคุณให้ละเอียด** เพื่อให้ทีมงานช่วยได้เร็วขึ้น"
        ),
        color=cat["color"],
        timestamp=datetime.now(),
    )
    embed.add_field(name="📂 หมวดหมู่",    value=cat["label"],              inline=True)
    embed.add_field(name="⚡ Priority",     value=PRIORITY_MAP.get(priority, priority), inline=True)
    embed.add_field(name="👤 ผู้เปิด Ticket", value=user.mention,           inline=True)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text="กดปุ่ม 'ปิด Ticket' เมื่อปัญหาได้รับการแก้ไขแล้ว")

    # Ping @support
    ping = ""
    if cfg and cfg.get("support_role_id"):
        role = guild.get_role(cfg["support_role_id"])
        if role:
            ping = role.mention

    await channel.send(
        content=ping or None,
        embed=embed,
        view=TicketControlView(),
    )

    await itx.followup.send(
        f"✅ สร้าง Ticket เรียบร้อยแล้วที่ {channel.mention}", ephemeral=True
    )


async def _close_ticket(
    channel: discord.TextChannel,
    closer: discord.Member,
    ticket: dict,
):
    """บันทึก transcript → log → DM rating → ลบห้อง"""
    guild = channel.guild
    cfg   = db.get_config(guild.id)

    # ─ สร้าง Transcript ─────────────────────────────────────────────────────
    html  = await generate_html(channel, ticket)
    html_bytes = html.encode("utf-8")

    # ─ ส่ง transcript ไปยัง log channel ────────────────────────────────────
    if cfg and cfg.get("transcript_channel_id"):
        log_ch = guild.get_channel(cfg["transcript_channel_id"])
        if log_ch:
            opener = guild.get_member(ticket["user_id"])
            log_embed = discord.Embed(
                title=f"📋 Transcript · {channel.name}",
                color=discord.Color.orange(),
                timestamp=datetime.now(),
            )
            log_embed.add_field(
                name="👤 ผู้เปิด",
                value=opener.mention if opener else f'<@{ticket["user_id"]}>',
                inline=True,
            )
            log_embed.add_field(name="🔒 ปิดโดย", value=closer.mention, inline=True)
            log_embed.add_field(
                name="📂 หมวดหมู่",
                value=CATS.get(ticket["category"], {}).get("label", ticket["category"]),
                inline=True,
            )
            await log_ch.send(
                embed=log_embed,
                file=discord.File(io.BytesIO(html_bytes), filename=f"{channel.name}.html"),
            )

    # ─ DM Rating ─────────────────────────────────────────────────────────────
    opener = guild.get_member(ticket["user_id"])
    if opener:
        try:
            r_embed = discord.Embed(
                title="⭐ ให้คะแนนการบริการ",
                description=(
                    f"Ticket **{channel.name}** ถูกปิดแล้ว\n"
                    "กรุณาให้คะแนนเพื่อช่วยให้เราปรับปรุงการบริการ"
                ),
                color=discord.Color.gold(),
            )
            await opener.send(embed=r_embed, view=RatingView(channel.id, opener.id))
        except discord.Forbidden:
            pass

    # ─ อัปเดต DB ──────────────────────────────────────────────────────────
    db.close_ticket(channel.id)

    # ─ แจ้งในห้อง แล้วลบ ──────────────────────────────────────────────────
    close_embed = discord.Embed(
        title="🔒 Ticket ถูกปิดแล้ว",
        description=f"ปิดโดย {closer.mention} • ห้องนี้จะถูกลบใน **5 วินาที**",
        color=discord.Color.red(),
    )
    await channel.send(
        embed=close_embed,
        file=discord.File(io.BytesIO(html_bytes), filename=f"{channel.name}.html"),
    )

    await asyncio.sleep(5)
    try:
        await channel.delete(reason=f"Ticket closed by {closer}")
    except discord.HTTPException:
        pass


# ════════════════════════════════════════════════════════════════════════════
#  Cog
# ════════════════════════════════════════════════════════════════════════════

class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # ลงทะเบียน persistent views ให้ bot จำ custom_id ข้ามรีสตาร์ท
        bot.add_view(CategorySelectView())
        bot.add_view(TicketControlView())

    # ── /setup ──────────────────────────────────────────────────────────────
    @app_commands.command(name="setup", description="🔧 ตั้งค่าและส่ง Panel ระบบ Ticket")
    @app_commands.default_permissions(administrator=True)
    async def cmd_setup(
        self,
        itx: discord.Interaction,
        support_role:       discord.Role,
        admin_role:         discord.Role,
        log_channel:        discord.TextChannel,
        transcript_channel: discord.TextChannel,
        vip_role:           discord.Role | None = None,
        cooldown_minutes:   int = 5,
    ):
        db.set_config(
            itx.guild.id,
            support_role_id=support_role.id,
            admin_role_id=admin_role.id,
            vip_role_id=vip_role.id if vip_role else None,
            log_channel_id=log_channel.id,
            transcript_channel_id=transcript_channel.id,
            cooldown_seconds=cooldown_minutes * 60,
        )

        vip_desc = (
            f"เฉพาะสมาชิก {vip_role.mention} เท่านั้น"
            if vip_role
            else "ช่องทางพิเศษสำหรับสมาชิก VIP"
        )

        embed = discord.Embed(
            title="🎫 ระบบสนับสนุน | Support Ticket",
            description=(
                "กดปุ่มด้านล่างเพื่อเปิด Ticket และรับความช่วยเหลือจากทีมงาน\n"
                "ทีมงานจะเข้ามาช่วยเหลือโดยเร็วที่สุด ⚡"
            ),
            color=discord.Color.blurple(),
        )
        for key, cat in CATS.items():
            desc = vip_desc if key == "vip" else cat["desc"]
            embed.add_field(name=cat["label"], value=desc, inline=False)
        embed.set_footer(
            text=f"Cooldown {cooldown_minutes} นาที • Powered by Ticket Bot"
        )

        await itx.channel.send(embed=embed, view=CategorySelectView())
        cfg_lines = [
            f"✅ ส่ง Panel Ticket เรียบร้อยแล้ว!",
            f"👮 Admin Role: {admin_role.mention}",
            f"🛡️ Support Role: {support_role.mention}",
            f"⭐ VIP Role: {vip_role.mention if vip_role else '`ไม่ได้ตั้งค่า (ทุกคนกดได้)`'}",
        ]
        await itx.response.send_message("\n".join(cfg_lines), ephemeral=True)

    # ── /ticket stats ────────────────────────────────────────────────────────
    @app_commands.command(name="stats", description="📊 ดูสถิติ Ticket ของ Server")
    @app_commands.default_permissions(manage_guild=True)
    async def cmd_stats(self, itx: discord.Interaction):
        s = db.get_stats(itx.guild.id)
        opens = db.get_open_tickets(itx.guild.id)

        avg  = s.get("avg_rating")
        avg_txt = f"`{avg:.1f}/5 ⭐`" if avg else "`ยังไม่มีคะแนน`"

        embed = discord.Embed(
            title="📊 Ticket Dashboard",
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        embed.add_field(name="📋 ทั้งหมด",  value=f'`{s.get("total", 0)}`',      inline=True)
        embed.add_field(name="🟢 เปิดอยู่", value=f'`{s.get("open_count", 0)}`', inline=True)
        embed.add_field(name="🔒 ปิดแล้ว",  value=f'`{s.get("closed_count", 0)}`', inline=True)
        embed.add_field(name="⭐ คะแนนเฉลี่ย", value=avg_txt, inline=True)

        if opens:
            lines = []
            for t in opens[:8]:
                ch = itx.guild.get_channel(t["channel_id"])
                pr = PRIORITY_MAP.get(t["priority"], "")
                lines.append(f"• {ch.mention if ch else '?'} {pr} — <@{t['user_id']}>")
            embed.add_field(
                name=f"🔓 เปิดอยู่ ({len(opens)} รายการ)",
                value="\n".join(lines) or "ไม่มี",
                inline=False,
            )

        await itx.response.send_message(embed=embed)

    # ── /add ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="add", description="➕ เพิ่มคนเข้า Ticket channel นี้")
    @app_commands.default_permissions(manage_channels=True)
    async def cmd_add(self, itx: discord.Interaction, member: discord.Member):
        if not db.get_ticket(itx.channel.id):
            return await itx.response.send_message("❌ ห้องนี้ไม่ใช่ Ticket", ephemeral=True)
        await itx.channel.set_permissions(
            member, view_channel=True, send_messages=True
        )
        await itx.response.send_message(f"✅ เพิ่ม {member.mention} เข้า Ticket แล้ว")

    # ── /remove ──────────────────────────────────────────────────────────────
    @app_commands.command(name="remove", description="➖ นำคนออกจาก Ticket channel นี้")
    @app_commands.default_permissions(manage_channels=True)
    async def cmd_remove(self, itx: discord.Interaction, member: discord.Member):
        if not db.get_ticket(itx.channel.id):
            return await itx.response.send_message("❌ ห้องนี้ไม่ใช่ Ticket", ephemeral=True)
        await itx.channel.set_permissions(member, overwrite=None)
        await itx.response.send_message(f"✅ นำ {member.mention} ออกจาก Ticket แล้ว")

    # ── /priority ────────────────────────────────────────────────────────────
    @app_commands.command(name="priority", description="⚡ เปลี่ยน Priority ของ Ticket")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.choices(level=[
        app_commands.Choice(name="🔴 สูง (High)",   value="high"),
        app_commands.Choice(name="🟡 ปกติ (Normal)", value="normal"),
        app_commands.Choice(name="🟢 ต่ำ (Low)",    value="low"),
    ])
    async def cmd_priority(self, itx: discord.Interaction, level: str):
        if not db.get_ticket(itx.channel.id):
            return await itx.response.send_message("❌ ห้องนี้ไม่ใช่ Ticket", ephemeral=True)
        db.set_priority(itx.channel.id, level)
        await itx.response.send_message(
            f"{PRIORITY_MAP[level]} เปลี่ยน Priority เป็น **{level}** แล้ว"
        )

    # ── /close ───────────────────────────────────────────────────────────────
    @app_commands.command(name="close", description="🔒 ปิด Ticket ปัจจุบัน")
    async def cmd_close(self, itx: discord.Interaction):
        ticket = db.get_ticket(itx.channel.id)
        if not ticket:
            return await itx.response.send_message("❌ ห้องนี้ไม่ใช่ Ticket", ephemeral=True)
        if not _can_manage(itx, ticket):
            return await itx.response.send_message(
                "❌ เฉพาะเจ้าของหรือแอดมินเท่านั้น", ephemeral=True
            )
        view = ConfirmCloseView(ticket)
        embed = discord.Embed(
            description="⚠️ **ยืนยันการปิด Ticket?**",
            color=discord.Color.orange(),
        )
        await itx.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketCog(bot))
                                      
