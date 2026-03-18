import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv
import asyncio
from aiohttp import web

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID'))

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ {bot.user} est connecté et prêt !')
    try:
        synced = await bot.tree.sync()
        print(f'✅ {len(synced)} commandes slash synchronisées')
    except Exception as e:
        print(f'❌ Erreur sync : {e}')

async def load_cogs():
    cogs = ['cogs.verification', 'cogs.rules', 'cogs.calendar', 'cogs.moderation', 'cogs.tickets']
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f'✅ Cog chargé : {cog}')
        except Exception as e:
            print(f'❌ Erreur chargement {cog} : {e}')

# Mini serveur HTTP pour Koyeb health check
async def health_check(request):
    return web.Response(text='OK')

async def start_webserver():
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8000)
    await site.start()
    print('✅ Health check server démarré sur port 8000')

async def main():
    async with bot:
        await load_cogs()
        await asyncio.gather(
            start_webserver(),
            bot.start(TOKEN)
        )

asyncio.run(main())