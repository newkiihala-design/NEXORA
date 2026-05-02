import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────
#  Bot Setup
# ─────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"\n{'='*45}")
    print(f"  🎫  Ticket Bot พร้อมใช้งานแล้ว!")
    print(f"  Bot: {bot.user} ({bot.user.id})")
    print(f"  Servers: {len(bot.guilds)}")
    print(f"{'='*45}\n")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="🎫 /setup เพื่อเริ่มระบบ Ticket"
        )
    )

    try:
        synced = await bot.tree.sync()
        print(f"✅  Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌  Sync error: {e}")


async def load_cogs():
    cogs_dir = "./cogs"
    for filename in os.listdir(cogs_dir):
        if filename.endswith(".py") and not filename.startswith("_"):
            cog_name = f"cogs.{filename[:-3]}"
            try:
                await bot.load_extension(cog_name)
                print(f"✅  Loaded: {cog_name}")
            except Exception as e:
                print(f"❌  Failed to load {cog_name}: {e}")


async def main():
    async with bot:
        await load_cogs()
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            raise ValueError("❌ DISCORD_TOKEN ไม่ถูกตั้งค่าใน .env!")
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
