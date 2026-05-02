# 🎫 Discord Ticket Bot

บอท Ticket สำหรับ Discord แบบครบครัน — สร้างด้วย `discord.py 2.x`

---

## ✨ ฟีเจอร์ทั้งหมด

| หมวด | ฟีเจอร์ |
|------|---------|
| **พื้นฐาน** | สร้าง Ticket ด้วยปุ่ม, 4 หมวดหมู่, ตั้งชื่ออัตโนมัติ, จำกัดสิทธิ์ |
| **เสริม** | Transcript HTML, Assign เคส, Cooldown, Embed UI, Auto-ping @Support |
| **ขั้นสูง** | Priority (High/Normal/Low), Rating ⭐, Dashboard Stats, /add /remove |

---

## 📁 โครงสร้างโปรเจกต์

```
ticket-bot/
├── main.py              ← จุดเริ่มต้นของบอท
├── cogs/
│   └── ticket.py        ← ระบบ Ticket ทั้งหมด (commands + views)
├── utils/
│   ├── database.py      ← SQLite database handler
│   └── transcript.py    ← สร้าง Transcript HTML
├── requirements.txt
├── Procfile             ← สำหรับ Railway
├── railway.json
├── .env.example
└── .gitignore
```

---

## 🚀 ขั้นตอนติดตั้ง

### 1. สร้างบอทใน Discord Developer Portal

1. ไปที่ [discord.com/developers/applications](https://discord.com/developers/applications)
2. กด **New Application** → ตั้งชื่อ → **Create**
3. ไปแท็บ **Bot** → **Add Bot**
4. เปิด **Privileged Gateway Intents** ทั้ง 3 ตัว:
   - `PRESENCE INTENT`
   - `SERVER MEMBERS INTENT`
   - `MESSAGE CONTENT INTENT`
5. คัดลอก **Token** เก็บไว้

### 2. เชิญบอทเข้า Server

ไปแท็บ **OAuth2 → URL Generator**:
- Scopes: `bot`, `applications.commands`
- Bot Permissions: `Administrator` (หรือกำหนดเองตามที่ต้องการ)
- คัดลอก URL แล้วเปิดในเบราว์เซอร์

### 3. ติดตั้งและรันในเครื่อง

```bash
# Clone หรือดาวน์โหลดโปรเจกต์
cd ticket-bot

# ติดตั้ง dependencies
pip install -r requirements.txt

# ตั้งค่า .env
cp .env.example .env
# แก้ไข .env ใส่ Token ของคุณ

# รันบอท
python main.py
```

---

## ☁️ Deploy บน Railway

### วิธีที่ 1: GitHub + Railway (แนะนำ)

1. **Push โค้ดขึ้น GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial ticket bot"
   git remote add origin https://github.com/your-username/ticket-bot.git
   git push -u origin main
   ```

2. **สร้าง Project บน Railway:**
   - ไปที่ [railway.app](https://railway.app) → **New Project**
   - เลือก **Deploy from GitHub repo**
   - เลือก repo `ticket-bot`

3. **ตั้งค่า Environment Variable:**
   - ไปแท็บ **Variables**
   - เพิ่ม: `DISCORD_TOKEN` = `your_token_here`

4. Railway จะ Deploy อัตโนมัติ ✅

### วิธีที่ 2: Railway CLI

```bash
npm install -g @railway/cli
railway login
railway init
railway up
railway variables set DISCORD_TOKEN=your_token_here
```

---

## ⚙️ คำสั่ง Slash Commands

| คำสั่ง | สิทธิ์ | คำอธิบาย |
|--------|--------|-----------|
| `/setup` | Administrator | ส่ง Panel Ticket และตั้งค่าระบบ |
| `/stats` | Manage Guild | ดู Dashboard สถิติ Ticket |
| `/close` | เจ้าของ / Staff | ปิด Ticket ปัจจุบัน |
| `/add @member` | Manage Channels | เพิ่มคนเข้า Ticket |
| `/remove @member` | Manage Channels | นำคนออกจาก Ticket |
| `/priority [level]` | Manage Channels | เปลี่ยน Priority: high / normal / low |

---

## 🔧 การใช้งาน /setup

```
/setup
  support_role: @Support          ← Role ที่จะรับ Ticket
  admin_role: @Admin              ← Role แอดมิน
  log_channel: #ticket-logs      ← ห้อง log
  transcript_channel: #transcripts ← ห้อง Transcript
  cooldown_minutes: 5            ← Cooldown (นาที)
```

หลัง `/setup` บอทจะส่ง Embed Panel ในห้องนั้นทันที

---

## 🎨 Transcript

- ไฟล์ `.html` สวยงาม ธีม Discord Dark
- มี avatar, embed, attachment
- ส่งให้ผู้ปิดผ่าน DM + บันทึกใน log channel

---

## 🤝 Contributing

Pull Request ยินดีต้อนรับ! กรุณาอ่าน [CONTRIBUTING.md](CONTRIBUTING.md)

---

## 📄 License

MIT License — ใช้งานได้อย่างอิสระ
