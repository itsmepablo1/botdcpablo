import asyncio
import discord
from discord.ext import commands
import sys, os

# Configure stdout for Windows/utf-8 compatibility
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(__file__))
from bot.config import DISCORD_TOKEN
from bot import database as db

COGS = [
    "bot.cogs.welcome",
    "bot.cogs.music",
    "bot.cogs.roles",
    "bot.cogs.autovoice",
    "bot.cogs.status",
    "bot.cogs.streaming",
]

intents = discord.Intents.default()
intents.members         = True
intents.message_content = True
intents.presences       = True
intents.voice_states    = True

def log(msg, fallback_msg):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(fallback_msg)

class BotDC(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await db.init_db()
        for cog in COGS:
            try:
                await self.load_extension(cog)
                log(f"  ✅ Loaded: {cog}", f"  [OK] Loaded: {cog}")
            except Exception as e:
                log(f"  ❌ Failed {cog}: {e}", f"  [ERROR] Failed {cog}: {e}")
        synced = await self.tree.sync()
        log(f"  🔄 Synced {len(synced)} slash commands.", f"  [SYNC] Synced {len(synced)} slash commands.")

    async def on_ready(self):
        sep = '=' * 45
        print(f"\n{sep}")
        log(f"  [BOT] {self.user} ({self.user.id})", f"  [BOT] {self.user} ({self.user.id})")
        log(f"  [SERVERS] {len(self.guilds)}", f"  [SERVERS] {len(self.guilds)}")
        log(f"  [USERS] {sum(g.member_count for g in self.guilds)}", f"  [USERS] {sum(g.member_count for g in self.guilds)}")
        print(f"{sep}\n")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} servers | /help"
            )
        )

    async def on_command_error(self, ctx, error):
        pass  # Suppress prefix command errors (using slash commands)

    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        msg = f"❌ Error: {str(error)}"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


async def main():
    bot = BotDC()
    async with bot:
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
