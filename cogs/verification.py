import discord
from discord.ext import commands
from discord import app_commands
import os
import random
import asyncio
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import json

verification_attempts = {}
STATS_FILE = 'data/verification_stats.json'

_rules_mention = None
_log_channel = None

def is_owner(user_id: int) -> bool:
    return user_id == int(os.getenv('OWNER_ID', 0))

def is_staff(member: discord.Member) -> bool:
    return is_owner(member.id) or any(r.name == 'MFJ Teams' for r in member.roles)

def load_stats():
    os.makedirs('data', exist_ok=True)
    if not os.path.exists(STATS_FILE):
        return {'sources': {}, 'trader_types': {}, 'total': 0, 'raw': []}
    with open(STATS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_stats(data):
    os.makedirs('data', exist_ok=True)
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def add_stat(source: str, trader_type: str, member_id: int, member_name: str):
    stats = load_stats()
    stats['total'] += 1
    stats['sources'][source] = stats['sources'].get(source, 0) + 1
    stats['trader_types'][trader_type] = stats['trader_types'].get(trader_type, 0) + 1
    if 'raw' not in stats:
        stats['raw'] = []
    stats['raw'].append({
        'id': member_id,
        'name': member_name,
        'source': source,
        'trader_type': trader_type,
        'date': datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    })
    save_stats(stats)

def generate_code():
    chars = 'ABCDEFGHJKLMNPQRTUVWXYZ2346789'
    return ''.join(random.choices(chars, k=5))

def generate_captcha_image(code: str) -> io.BytesIO:
    width, height = 380, 120
    img = Image.new('RGB', (width, height), color=(13, 17, 23))
    draw = ImageDraw.Draw(img)

    for _ in range(6):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        color = random.choice([(0, 212, 168), (245, 158, 11), (80, 80, 100)])
        draw.line([(x1, y1), (x2, y2)], fill=color, width=1)

    for _ in range(150):
        x = random.randint(0, width)
        y = random.randint(0, height)
        draw.point((x, y), fill=(0, 212, 168))

    try:
        font = ImageFont.truetype("arial.ttf", 62)
    except:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 62)
        except:
            font = ImageFont.load_default()

    colors = [
        (0, 212, 168), (245, 158, 11), (255, 255, 255),
        (0, 200, 150), (255, 220, 50),
    ]

    total_width = len(code) * 68
    x_start = (width - total_width) // 2 + 10
    x_offset = x_start

    for char in code:
        color = random.choice(colors)
        y_offset = random.randint(10, 30)
        char_img = Image.new('RGBA', (65, 80), (0, 0, 0, 0))
        char_draw = ImageDraw.Draw(char_img)
        char_draw.text((5, 0), char, font=font, fill=color)
        angle = random.randint(-15, 15)
        char_img = char_img.rotate(angle, expand=True)
        img.paste(char_img, (x_offset, y_offset), char_img)
        x_offset += 68

    img = img.filter(ImageFilter.SMOOTH)
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (width-1, height-1)], outline=(0, 212, 168), width=2)

    try:
        small_font = ImageFont.truetype("arial.ttf", 11)
    except:
        try:
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
        except:
            small_font = ImageFont.load_default()

    draw.text((6, height-16), 'MarketFlow Journal', font=small_font, fill=(0, 212, 168))

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


def generate_stats_image(stats: dict) -> io.BytesIO:
    width, height = 800, 500
    bg_color = (13, 17, 23)
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    try:
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
        font_med = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
    except:
        font_big = ImageFont.load_default()
        font_med = font_big
        font_small = font_big

    palette = [
        (0, 212, 168), (245, 158, 11), (239, 68, 68),
        (99, 102, 241), (236, 72, 153), (16, 185, 129),
        (251, 191, 36), (59, 130, 246), (167, 139, 250),
        (248, 113, 113),
    ]

    # Titre
    draw.text((width//2, 30), 'MarketFlow Journal — Community Stats',
              font=font_big, fill=(0, 212, 168), anchor='mm')
    draw.text((width//2, 58), f'Total verified members: {stats["total"]}',
              font=font_med, fill=(180, 180, 180), anchor='mm')
    draw.line([(40, 72), (width-40, 72)], fill=(0, 212, 168), width=1)

    def draw_bars(x, y, w, data_dict, title, color_offset=0):
        draw.text((x + w//2, y), title, font=font_med, fill=(255, 255, 255), anchor='mm')
        y += 25
        if not data_dict:
            draw.text((x + w//2, y + 30), 'No data yet',
                     font=font_small, fill=(120, 120, 140), anchor='mm')
            return

        total = sum(data_dict.values())
        items = sorted(data_dict.items(), key=lambda x: x[1], reverse=True)[:8]
        bar_h = 22
        gap = 8

        for i, (label, value) in enumerate(items):
            color = palette[(i + color_offset) % len(palette)]
            pct = value / total
            bar_w = int(pct * (w - 120))

            draw.rectangle(
                [x + 110, y + i*(bar_h+gap),
                 x + 110 + max(bar_w, 4), y + i*(bar_h+gap) + bar_h],
                fill=color
            )

            label_short = label[:14] if len(label) > 14 else label
            draw.text((x + 105, y + i*(bar_h+gap) + bar_h//2),
                     label_short, font=font_small, fill=(220, 220, 220), anchor='rm')

            draw.text((x + 115 + max(bar_w, 4) + 5, y + i*(bar_h+gap) + bar_h//2),
                     f'{value} ({round(pct*100, 1)}%)',
                     font=font_small, fill=(180, 180, 180), anchor='lm')

    draw_bars(40, 95, 340, stats.get('sources', {}), 'How they found us', 0)
    draw.line([(width//2, 80), (width//2, height-30)], fill=(25, 32, 42), width=1)
    draw_bars(width//2 + 20, 95, 340, stats.get('trader_types', {}), 'Trader experience', 4)

    draw.line([(40, height-28), (width-40, height-28)], fill=(0, 212, 168), width=1)
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    draw.text((width//2, height-14),
              f'Generated {now} • MarketFlow Journal',
              font=font_small, fill=(80, 85, 100), anchor='mm')

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


def get_user_data(user_id):
    if user_id not in verification_attempts:
        verification_attempts[user_id] = {
            'attempts': 0,
            'blocked_until': None,
            'code': None,
            'captcha_done': False,
            'source': None
        }
    return verification_attempts[user_id]


async def log_action(embed: discord.Embed):
    global _log_channel
    if _log_channel:
        try:
            await _log_channel.send(embed=embed)
        except:
            pass


class TraderTypeView(discord.ui.View):
    def __init__(self, user_id: int, source: str):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.source = source

    async def handle_trader(self, interaction: discord.Interaction, trader_type: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('❌ Not for you.', ephemeral=True)
            return

        global _rules_mention
        guild = interaction.guild
        member = interaction.user
        rules_mention = _rules_mention or '#rules'

        embed = discord.Embed(
            title='✅ Almost there!',
            description=(
                f'Head over to {rules_mention} 📜\n\n'
                'Read and accept the rules to unlock the full server.\n'
                '**One last step!**'
            ),
            color=0x00d4a8
        )
        embed.set_footer(text='MarketFlow Journal — Verification System')
        await interaction.response.edit_message(embed=embed, view=None)

        async def background():
            try:
                verif_role = discord.utils.get(guild.roles, name='MFJ Verification')
                if verif_role:
                    await member.add_roles(verif_role)
                else:
                    print('❌ Rôle MFJ Verification introuvable !')

                add_stat(self.source, trader_type, member.id, str(member))

                if self.user_id in verification_attempts:
                    del verification_attempts[self.user_id]

                embed_log = discord.Embed(title='🔐 Captcha Verified — Pending Rules', color=0xf59e0b)
                embed_log.add_field(name='Member', value=f'{member.mention} (`{member.id}`)', inline=False)
                embed_log.add_field(name='How they found us', value=self.source, inline=False)
                embed_log.add_field(name='Trader type', value=trader_type, inline=False)
                embed_log.set_footer(text='MarketFlow Journal — Verification System')
                await log_action(embed_log)
            except Exception as e:
                print(f'❌ Background error: {e}')

        asyncio.ensure_future(background())
        self.stop()

    @discord.ui.button(label='Beginner', style=discord.ButtonStyle.secondary)
    async def beginner(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_trader(interaction, 'Beginner')

    @discord.ui.button(label='Intermediate', style=discord.ButtonStyle.secondary)
    async def intermediate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_trader(interaction, 'Intermediate')

    @discord.ui.button(label='Prop Trader', style=discord.ButtonStyle.success)
    async def prop_trader(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_trader(interaction, 'Prop Trader')

    @discord.ui.button(label='Full-time', style=discord.ButtonStyle.primary)
    async def full_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_trader(interaction, 'Full-time')

    @discord.ui.button(label='Other', style=discord.ButtonStyle.secondary)
    async def other_trader(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_trader(interaction, 'Other')


class SourceView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id

    async def handle_source(self, interaction: discord.Interaction, source: str):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('❌ Not for you.', ephemeral=True)
            return

        embed = discord.Embed(
            title='📊 What type of trader are you?',
            description='Select the option that best describes you.',
            color=0x00d4a8
        )
        embed.set_footer(text='MarketFlow Journal — Step 2/2')
        await interaction.response.edit_message(
            embed=embed,
            view=TraderTypeView(user_id=self.user_id, source=source)
        )
        self.stop()

    @discord.ui.button(label='Twitter / X', style=discord.ButtonStyle.secondary)
    async def twitter(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_source(interaction, 'Twitter / X')

    @discord.ui.button(label='Discord', style=discord.ButtonStyle.secondary)
    async def discord_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_source(interaction, 'Discord')

    @discord.ui.button(label='Friend', style=discord.ButtonStyle.secondary)
    async def friend(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_source(interaction, 'Friend')

    @discord.ui.button(label='YouTube', style=discord.ButtonStyle.secondary)
    async def youtube(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_source(interaction, 'YouTube')

    @discord.ui.button(label='Instagram', style=discord.ButtonStyle.secondary)
    async def instagram(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_source(interaction, 'Instagram')

    @discord.ui.button(label='TikTok', style=discord.ButtonStyle.secondary)
    async def tiktok(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_source(interaction, 'TikTok')

    @discord.ui.button(label='Google', style=discord.ButtonStyle.secondary)
    async def google(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_source(interaction, 'Google')

    @discord.ui.button(label='Reddit', style=discord.ButtonStyle.secondary)
    async def reddit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_source(interaction, 'Reddit')

    @discord.ui.button(label='Telegram', style=discord.ButtonStyle.secondary)
    async def telegram(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_source(interaction, 'Telegram')

    @discord.ui.button(label='Other', style=discord.ButtonStyle.secondary)
    async def other(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_source(interaction, 'Other')


class CaptchaCodeModal(discord.ui.Modal, title='MarketFlow Journal — Enter Code'):
    def __init__(self, code: str):
        super().__init__()
        self.code = code
        self.captcha_input = discord.ui.TextInput(
            label='Enter the 5-character code',
            placeholder='Uppercase or lowercase, both work...',
            required=True,
            max_length=5,
            min_length=5
        )
        self.add_item(self.captcha_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        guild = interaction.guild
        member = interaction.user
        data = get_user_data(user_id)

        if data['blocked_until'] and datetime.utcnow() < data['blocked_until']:
            remaining = int((data['blocked_until'] - datetime.utcnow()).total_seconds() / 60)
            await interaction.response.send_message(
                f'❌ Blocked for **{remaining} minute(s)**.',
                ephemeral=True
            )
            return

        user_input = self.captcha_input.value.strip().upper()

        if data['code'] is None or user_input != data['code']:
            data['attempts'] += 1
            remaining_attempts = 3 - data['attempts']

            if data['attempts'] >= 3:
                data['blocked_until'] = datetime.utcnow() + timedelta(minutes=5)
                data['attempts'] = 0
                data['code'] = None
                data['captcha_done'] = False
                await interaction.response.send_message(
                    '❌ **3 failed attempts.** Blocked for **5 minutes**.',
                    ephemeral=True
                )
                embed_fail = discord.Embed(title='⚠️ Verification Failed', color=0xef4444)
                embed_fail.add_field(name='Member', value=f'{member.mention} (`{member.id}`)', inline=False)
                embed_fail.add_field(name='Reason', value='Blocked after 3 failed attempts', inline=False)
                embed_fail.set_footer(text='MarketFlow Journal — Verification System')
                asyncio.ensure_future(log_action(embed_fail))
            else:
                await interaction.response.send_message(
                    f'❌ Wrong code. **{remaining_attempts} attempt(s)** remaining.\nClick **Start Verification** for a new captcha.',
                    ephemeral=True
                )
            return

        data['captcha_done'] = True
        data['code'] = None

        embed = discord.Embed(
            title='✅ Captcha Passed! — Step 1/2',
            description='How did you discover **MarketFlow Journal**?',
            color=0x00d4a8
        )
        embed.set_footer(text='MarketFlow Journal — Verification System')
        await interaction.response.send_message(
            embed=embed,
            view=SourceView(user_id=user_id),
            ephemeral=True
        )


class CaptchaAnswerView(discord.ui.View):
    def __init__(self, code: str):
        super().__init__(timeout=300)
        self.code = code

    @discord.ui.button(
        label='Enter the code →',
        style=discord.ButtonStyle.primary
    )
    async def enter_code(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        data = get_user_data(user_id)

        if data['blocked_until'] and datetime.utcnow() < data['blocked_until']:
            remaining = int((data['blocked_until'] - datetime.utcnow()).total_seconds() / 60)
            await interaction.response.send_message(
                f'❌ Blocked for **{remaining} minute(s)**.',
                ephemeral=True
            )
            return

        if data['code'] != self.code:
            await interaction.response.send_message(
                '❌ Captcha expired. Click **Start Verification** to get a new one.',
                ephemeral=True
            )
            return

        await interaction.response.send_modal(CaptchaCodeModal(code=self.code))


class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label='Start Verification ✅',
        style=discord.ButtonStyle.success,
        custom_id='start_verification'
    )
    async def start_verification(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        guild = interaction.guild

        membre_role = discord.utils.get(guild.roles, name='MFJ Membre')
        if membre_role and membre_role in interaction.user.roles:
            await interaction.response.send_message('✅ You are already a member!', ephemeral=True)
            return

        verif_role = discord.utils.get(guild.roles, name='MFJ Verification')
        if verif_role and verif_role in interaction.user.roles:
            rules_mention = _rules_mention or '#rules'
            await interaction.response.send_message(
                f'✅ Captcha already completed! Go to {rules_mention} and accept the rules.',
                ephemeral=True
            )
            return

        existing = verification_attempts.get(user_id, {})
        verification_attempts[user_id] = {
            'attempts': existing.get('attempts', 0),
            'blocked_until': existing.get('blocked_until', None),
            'code': None,
            'captcha_done': False,
            'source': None
        }
        data = verification_attempts[user_id]

        if data['blocked_until'] and datetime.utcnow() < data['blocked_until']:
            remaining = int((data['blocked_until'] - datetime.utcnow()).total_seconds() / 60)
            await interaction.response.send_message(
                f'❌ Blocked for **{remaining} minute(s)**.',
                ephemeral=True
            )
            return

        code = generate_code()
        data['code'] = code

        captcha_buffer = generate_captcha_image(code)
        file = discord.File(captcha_buffer, filename='captcha.png')

        embed = discord.Embed(
            title='🔐 Captcha Verification',
            description=(
                'Look at the image carefully.\n'
                'Click **"Enter the code →"** and type the **5 characters** exactly.\n'
                '*(uppercase or lowercase, both work)*\n\n'
                '⚠️ **3 attempts max — 5 min cooldown if exceeded**'
            ),
            color=0x00d4a8
        )
        embed.set_image(url='attachment://captcha.png')
        embed.set_footer(text='MarketFlow Journal — Verification System')

        await interaction.response.send_message(
            embed=embed,
            file=file,
            view=CaptchaAnswerView(code=code),
            ephemeral=True
        )


class Verification(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(VerificationView())

    @commands.Cog.listener()
    async def on_ready(self):
        global _rules_mention, _log_channel
        print('✅ Cog Verification prêt')

        guild = self.bot.get_guild(int(os.getenv('GUILD_ID')))
        if not guild:
            return

        rules_channel_id = int(os.getenv('RULES_CHANNEL_ID', 0))
        rules_channel = guild.get_channel(rules_channel_id)
        if rules_channel:
            _rules_mention = rules_channel.mention
            print(f'✅ Rules cached: {_rules_mention}')

        log_channel_id = int(os.getenv('LOG_CHANNEL_ID', 0))
        _log_channel = guild.get_channel(log_channel_id)
        print(f'✅ Log channel cached: {_log_channel}')

        verif_channel_id = int(os.getenv('VERIFICATION_CHANNEL_ID', 0))
        verif_channel = guild.get_channel(verif_channel_id)
        if not verif_channel:
            return

        messages = [msg async for msg in verif_channel.history(limit=10)]
        bot_messages = [m for m in messages if m.author == self.bot.user]

        if len(bot_messages) == 1:
            print('✅ Message de vérification déjà présent')
            return

        await verif_channel.purge(limit=100, check=lambda m: m.author == self.bot.user)

        embed = discord.Embed(
            title='🔐 MarketFlow Journal — Trader Verification',
            description=(
                'Welcome to **MarketFlow Journal**.\n\n'
                'To gain full access to the server, please complete the verification below.\n\n'
                '**This takes less than 30 seconds.**'
            ),
            color=0x00d4a8
        )
        embed.add_field(
            name='Why verify?',
            value='We verify all members to maintain a high-quality trading community.',
            inline=False
        )
        embed.set_footer(text='MarketFlow Journal — Verification System')
        await verif_channel.send(embed=embed, view=VerificationView())

    @app_commands.command(name='setup_verification', description='Poste le message de vérification')
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_verification(self, interaction: discord.Interaction):
        await interaction.response.send_message('⏳ Setup en cours...', ephemeral=True)
        await interaction.channel.purge(limit=100, check=lambda m: m.author == self.bot.user)

        embed = discord.Embed(
            title='🔐 MarketFlow Journal — Trader Verification',
            description=(
                'Welcome to **MarketFlow Journal**.\n\n'
                'To gain full access to the server, please complete the verification below.\n\n'
                '**This takes less than 30 seconds.**'
            ),
            color=0x00d4a8
        )
        embed.add_field(
            name='Why verify?',
            value='We verify all members to maintain a high-quality trading community.',
            inline=False
        )
        embed.set_footer(text='MarketFlow Journal — Verification System')
        await interaction.channel.send(embed=embed, view=VerificationView())

    @app_commands.command(name='stats', description='Statistiques marketing des membres vérifiés')
    async def stats(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                '❌ You do not have permission to use this command.',
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        stats = load_stats()

        if stats['total'] == 0:
            await interaction.followup.send('📊 No verification data yet.', ephemeral=True)
            return

        loop = asyncio.get_event_loop()
        stats_buffer = await loop.run_in_executor(None, generate_stats_image, stats)
        file = discord.File(stats_buffer, filename='stats.png')

        embed = discord.Embed(
            title='📊 MarketFlow Journal — Verification Stats',
            description=f'**{stats["total"]}** total verified members',
            color=0x00d4a8
        )
        embed.set_image(url='attachment://stats.png')
        embed.set_footer(text='MarketFlow Journal — Staff Only • /reset_stats to clear')
        await interaction.followup.send(embed=embed, file=file, ephemeral=True)

        # Poste aussi dans le salon stats staff
        stats_channel_id = int(os.getenv('STATS_CHANNEL_ID', 0))
        if stats_channel_id:
            stats_channel = interaction.guild.get_channel(stats_channel_id)
            if stats_channel:
                stats_buffer2 = await loop.run_in_executor(None, generate_stats_image, stats)
                file2 = discord.File(stats_buffer2, filename='stats.png')
                embed2 = discord.Embed(
                    title='📊 MarketFlow Journal — Verification Stats',
                    description=f'**{stats["total"]}** total verified members',
                    color=0x00d4a8
                )
                embed2.set_image(url='attachment://stats.png')
                embed2.set_footer(text=f'MarketFlow Journal — {datetime.utcnow().strftime("%b %d at %H:%M UTC")}')
                await stats_channel.send(embed=embed2, file=file2)

    @app_commands.command(name='reset_stats', description='Réinitialise toutes les stats')
    async def reset_stats(self, interaction: discord.Interaction):
        if not is_owner(interaction.user.id):
            await interaction.response.send_message(
                '❌ You do not have permission to use this command.',
                ephemeral=True
            )
            return
        save_stats({'sources': {}, 'trader_types': {}, 'total': 0, 'raw': []})
        await interaction.response.send_message(
            '✅ All verification stats have been reset.',
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Verification(bot))