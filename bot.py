import discord
from discord import app_commands
from discord.ext import commands
import os
from dotenv import load_dotenv

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

@bot.tree.command(name='setup_server', description='Setup complet du serveur MarketFlow Journal')
@app_commands.checks.has_permissions(administrator=True)
async def setup_server(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild

    await interaction.followup.send('⏳ Setup en cours...', ephemeral=True)

    # Supprime tous les channels existants
    for channel in guild.channels:
        try:
            await channel.delete()
        except:
            pass

    # Crée les rôles
    roles = {}
    role_configs = [
        ('MFJ Membre', 0xffffff, False),
        ('MFJ Trader Vérifié', 0x00d4a8, False),
        ('MFJ Teams', 0xf59e0b, True),
        ('MFJ Owner', 0xef4444, True),
        ('Muted', 0x6b7280, False),
    ]

    for name, color, hoist in role_configs:
        existing = discord.utils.get(guild.roles, name=name)
        if not existing:
            role = await guild.create_role(
                name=name,
                color=discord.Color(color),
                hoist=hoist
            )
            roles[name] = role
        else:
            roles[name] = existing

    # Permissions de base
    everyone = guild.default_role
    membre_role = roles.get('MFJ Membre')

    # Overwrites verification only — visible pour tout le monde
    overwrites_verification = {
        everyone: discord.PermissionOverwrite(
            read_messages=True,
            send_messages=False
        ),
        membre_role: discord.PermissionOverwrite(
            read_messages=False
        )
    }

    # Overwrites locked — invisible avant vérif
    overwrites_locked = {
        everyone: discord.PermissionOverwrite(read_messages=False),
        membre_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }

    # Overwrites read only
    overwrites_readonly = {
        everyone: discord.PermissionOverwrite(read_messages=False),
        membre_role: discord.PermissionOverwrite(read_messages=True, send_messages=False)
    }

    # Overwrites staff only
    overwrites_staff = {
        everyone: discord.PermissionOverwrite(read_messages=False),
        roles.get('MFJ Teams'): discord.PermissionOverwrite(read_messages=True),
        roles.get('MFJ Owner'): discord.PermissionOverwrite(read_messages=True)
    }

    # --- CATÉGORIE BIENVENUE ---
    cat_welcome = await guild.create_category('📌 BIENVENUE', overwrites={everyone: discord.PermissionOverwrite(read_messages=True)})
    ch_verif = await guild.create_text_channel('🎫┃verification', category=cat_welcome, overwrites=overwrites_verification)
    await guild.create_text_channel('📜┃rules', category=cat_welcome, overwrites=overwrites_locked)

    # --- CATÉGORIE INFORMATIONS ---
    cat_info = await guild.create_category('📣 INFORMATIONS', overwrites={everyone: discord.PermissionOverwrite(read_messages=False), membre_role: discord.PermissionOverwrite(read_messages=True)})
    await guild.create_text_channel('📣┃announcements', category=cat_info, overwrites=overwrites_readonly)
    await guild.create_text_channel('📅┃economic-calendar', category=cat_info, overwrites=overwrites_readonly)
    await guild.create_text_channel('🆕┃updates', category=cat_info, overwrites=overwrites_readonly)

    # --- CATÉGORIE COMMUNAUTÉ ---
    cat_community = await guild.create_category('💬 COMMUNAUTÉ', overwrites={everyone: discord.PermissionOverwrite(read_messages=False), membre_role: discord.PermissionOverwrite(read_messages=True)})
    await guild.create_text_channel('🌐┃general-en', category=cat_community, overwrites=overwrites_locked)
    await guild.create_text_channel('🇫🇷┃general-fr', category=cat_community, overwrites=overwrites_locked)
    await guild.create_text_channel('💡┃trading-ideas', category=cat_community, overwrites=overwrites_locked)

    # --- CATÉGORIE TRADING ---
    cat_trading = await guild.create_category('📊 TRADING', overwrites={everyone: discord.PermissionOverwrite(read_messages=False), membre_role: discord.PermissionOverwrite(read_messages=True)})
    await guild.create_text_channel('📈┃analyses', category=cat_trading, overwrites=overwrites_locked)
    await guild.create_text_channel('🧠┃psychology', category=cat_trading, overwrites=overwrites_locked)
    await guild.create_text_channel('❓┃questions', category=cat_trading, overwrites=overwrites_locked)

    # --- CATÉGORIE MEMBRES ---
    cat_members = await guild.create_category('🏆 MEMBRES', overwrites={everyone: discord.PermissionOverwrite(read_messages=False), membre_role: discord.PermissionOverwrite(read_messages=True)})
    await guild.create_text_channel('🥇┃performance', category=cat_members, overwrites=overwrites_locked)
    await guild.create_text_channel('📓┃journal-showcase', category=cat_members, overwrites=overwrites_locked)

    # --- CATÉGORIE SUPPORT ---
    cat_support = await guild.create_category('🎫 SUPPORT', overwrites={everyone: discord.PermissionOverwrite(read_messages=False), membre_role: discord.PermissionOverwrite(read_messages=True)})
    await guild.create_text_channel('🎫┃support-ticket', category=cat_support, overwrites=overwrites_locked)
    await guild.create_text_channel('📞┃contact', category=cat_support, overwrites=overwrites_readonly)

    # --- CATÉGORIE STAFF ---
    cat_staff = await guild.create_category('🔒 STAFF ONLY', overwrites=overwrites_staff)
    ch_logs = await guild.create_text_channel('⚙️┃mod-logs', category=cat_staff, overwrites=overwrites_staff)
    await guild.create_text_channel('🛡️┃staff-chat', category=cat_staff, overwrites=overwrites_staff)

    # Met à jour le .env avec les IDs
    print(f'VERIFICATION_CHANNEL_ID={ch_verif.id}')
    print(f'LOG_CHANNEL_ID={ch_logs.id}')

    await interaction.followup.send(
        f'✅ **Serveur MarketFlow Journal configuré avec succès !**\n\n'
        f'📌 Mets à jour ton `.env` :\n'
        f'`VERIFICATION_CHANNEL_ID={ch_verif.id}`\n'
        f'`LOG_CHANNEL_ID={ch_logs.id}`',
        ephemeral=True
    )

async def load_cogs():
    cogs = ['cogs.verification', 'cogs.rules', 'cogs.calendar', 'cogs.moderation', 'cogs.tickets']
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f'✅ Cog chargé : {cog}')
        except Exception as e:
            print(f'❌ Erreur chargement {cog} : {e}')

async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

import asyncio
import discord
from discord import app_commands
asyncio.run(main())