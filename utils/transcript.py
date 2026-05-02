import discord
from datetime import datetime


CATEGORY_LABELS = {
    "problem": "🔴 แจ้งปัญหา",
    "payment": "💰 เติมเงิน",
    "general": "💬 สอบถามทั่วไป",
    "vip":     "⭐ VIP Support",
}

PRIORITY_LABELS = {
    "high":   "🔴 สูง",
    "normal": "🟡 ปกติ",
    "low":    "🟢 ต่ำ",
}


async def generate_html(channel: discord.TextChannel, ticket: dict) -> str:
    messages: list[discord.Message] = []
    async for msg in channel.history(limit=None, oldest_first=True):
        messages.append(msg)

    cat  = CATEGORY_LABELS.get(ticket.get("category", ""), ticket.get("category", ""))
    pri  = PRIORITY_LABELS.get(ticket.get("priority", "normal"), "🟡 ปกติ")
    now  = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    created = ticket.get("created_at", "")[:19].replace("T", " ")

    rows = ""
    for msg in messages:
        avatar = str(msg.author.display_avatar.url)
        is_bot = '<span class="badge">BOT</span>' if msg.author.bot else ""
        ts     = msg.created_at.strftime("%d/%m/%Y %H:%M:%S")
        text   = ""

        if msg.content:
            safe = (msg.content
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;"))
            text += f'<p class="msg-text">{safe}</p>'

        for emb in msg.embeds:
            title = emb.title or ""
            desc  = emb.description or ""
            color = f"#{emb.colour.value:06x}" if emb.colour else "#5865f2"
            text += f'<div class="embed" style="border-color:{color}"><strong>{title}</strong><br>{desc}</div>'

        for att in msg.attachments:
            if att.content_type and att.content_type.startswith("image"):
                text += f'<div class="att"><img src="{att.url}" alt="{att.filename}"></div>'
            else:
                text += f'<div class="att">📎 <a href="{att.url}">{att.filename}</a></div>'

        rows += f"""
        <div class="msg">
          <img class="av" src="{avatar}" onerror="this.src='https://cdn.discordapp.com/embed/avatars/0.png'">
          <div class="body">
            <div class="hdr">
              <span class="name">{msg.author.display_name}</span>{is_bot}
              <span class="ts">{ts}</span>
            </div>
            {text if text else '<p class="msg-text muted">[ไม่มีข้อความ]</p>'}
          </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Transcript · {channel.name}</title>
<style>
:root{{
  --bg:#1e1f22;--surface:#2b2d31;--surface2:#313338;
  --border:#3f4147;--text:#dbdee1;--muted:#80848e;
  --accent:#5865f2;--green:#23a55a;--red:#f23f43;--gold:#f0b232;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;font-size:15px}}
a{{color:#00a8fc;text-decoration:none}}
.header{{background:var(--surface);border-bottom:1px solid var(--border);padding:24px 32px}}
.header h1{{font-size:1.4rem;font-weight:700;color:#fff;margin-bottom:6px}}
.ch{{color:var(--muted);font-size:.9rem;margin-bottom:16px}}
.meta{{display:flex;flex-wrap:wrap;gap:10px}}
.chip{{background:var(--surface2);border:1px solid var(--border);border-radius:6px;
       padding:6px 14px;font-size:.82rem}}
.chip b{{color:#fff}}
.messages{{padding:20px 32px;max-width:900px;margin:0 auto}}
.msg{{display:flex;gap:14px;padding:8px 4px;border-radius:6px;transition:.15s}}
.msg:hover{{background:var(--surface2)}}
.av{{width:40px;height:40px;border-radius:50%;flex-shrink:0;object-fit:cover}}
.body{{flex:1;min-width:0}}
.hdr{{display:flex;align-items:baseline;gap:8px;margin-bottom:3px;flex-wrap:wrap}}
.name{{font-weight:600;color:#fff}}
.badge{{background:var(--accent);color:#fff;font-size:.6rem;font-weight:700;
        padding:1px 5px;border-radius:4px;letter-spacing:.5px}}
.ts{{font-size:.75rem;color:var(--muted)}}
.msg-text{{color:var(--text);line-height:1.5;word-break:break-word;white-space:pre-wrap}}
.muted{{color:var(--muted);font-style:italic}}
.embed{{border-left:4px solid var(--accent);background:var(--surface);
        border-radius:0 4px 4px 0;padding:10px 14px;margin-top:6px;
        font-size:.9rem;line-height:1.5}}
.att{{margin-top:6px}}
.att img{{max-width:400px;border-radius:6px;display:block}}
.footer{{background:var(--surface);border-top:1px solid var(--border);
         padding:14px 32px;text-align:center;color:var(--muted);font-size:.8rem}}
</style>
</head>
<body>
<div class="header">
  <h1>🎫 Ticket Transcript</h1>
  <div class="ch">#{channel.name}</div>
  <div class="meta">
    <div class="chip"><b>หมวดหมู่</b> {cat}</div>
    <div class="chip"><b>Priority</b> {pri}</div>
    <div class="chip"><b>เปิดเมื่อ</b> {created}</div>
    <div class="chip"><b>ปิดเมื่อ</b> {now}</div>
    <div class="chip"><b>ข้อความ</b> {len(messages)} รายการ</div>
  </div>
</div>
<div class="messages">
{rows}
</div>
<div class="footer">Transcript สร้างโดย Ticket Bot · {now}</div>
</body>
</html>"""
  
