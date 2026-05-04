import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
import re

def is_owner(user_id: int) -> bool:
    return user_id == int(os.getenv('OWNER_ID', 0))

def is_staff(member: discord.Member) -> bool:
    return is_owner(member.id) or any(r.name == 'MFJ Teams' for r in member.roles)

CURRENCY_FLAGS = {
    'USD': '🇺🇸', 'EUR': '🇪🇺', 'GBP': '🇬🇧',
    'JPY': '🇯🇵', 'CAD': '🇨🇦', 'AUD': '🇦🇺',
    'CHF': '🇨🇭', 'NZD': '🇳🇿'
}

DAY_ORDER = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
DAY_EMOJIS = {
    'Monday': '1️⃣', 'Tuesday': '2️⃣', 'Wednesday': '3️⃣',
    'Thursday': '4️⃣', 'Friday': '5️⃣',
}
DAY_COLORS = {
    'Monday': 0x00d4a8, 'Tuesday': 0x00b894,
    'Wednesday': 0x00a381, 'Thursday': 0x00916e, 'Friday': 0x007f5c,
}

# Mapping keywords → currency
CURRENCY_DETECT = {
    # USD
    'us ': 'USD', 'usd': 'USD', 'dollar': 'USD',
    'fed ': 'USD', 'fomc': 'USD', 'federal reserve': 'USD', 'powell': 'USD',
    'american': 'USD', 'usa': 'USD',
    # EUR
    'eur': 'EUR', 'euro': 'EUR', 'ecb': 'EUR', 'lagarde': 'EUR',
    'eurozone': 'EUR', 'euro zone': 'EUR', 'euro area': 'EUR',
    'german': 'EUR', 'germany': 'EUR', 'french': 'EUR', 'france': 'EUR',
    'italian': 'EUR', 'italy': 'EUR', 'spanish': 'EUR', 'spain': 'EUR',
    'dutch': 'EUR', 'belgium': 'EUR', 'portuguese': 'EUR',
    # GBP
    'gbp': 'GBP', 'pound': 'GBP', 'boe': 'GBP', 'bank of england': 'GBP',
    'uk ': 'GBP', 'u.k.': 'GBP', 'british': 'GBP', 'england': 'GBP',
    # JPY
    'jpy': 'JPY', 'yen': 'JPY', 'boj': 'JPY', 'bank of japan': 'JPY',
    'japan': 'JPY', 'japanese': 'JPY',
    # CAD
    'cad': 'CAD', 'boc': 'CAD', 'bank of canada': 'CAD',
    'canada': 'CAD', 'canadian': 'CAD',
    # AUD
    'aud': 'AUD', 'rba': 'AUD', 'reserve bank of australia': 'AUD',
    'australia': 'AUD', 'australian': 'AUD',
    # CHF
    'chf': 'CHF', 'snb': 'CHF', 'swiss': 'CHF', 'switzerland': 'CHF',
    # NZD
    'nzd': 'NZD', 'new zealand': 'NZD', 'rbnz': 'NZD',
}

HIGH_IMPACT_KEYWORDS = [
    'interest rate', 'rate decision', 'rate hike', 'rate cut',
    'fed ', 'fomc', 'federal reserve', 'powell',
    'ecb', 'boe', 'boj', 'boc', 'rba', 'snb',
    'nfp', 'non-farm', 'nonfarm', 'payroll',
    'cpi', 'inflation rate',
    'gdp',
    'unemployment rate',
    'pmi',
]

_calendar_messages = {}
_last_events_data = {}


def detect_currency(text: str) -> str:
    text_lower = ' ' + text.lower() + ' '
    for keyword, currency in CURRENCY_DETECT.items():
        if keyword in text_lower:
            return currency
    return ''


def is_high_impact(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in HIGH_IMPACT_KEYWORDS)


def parse_fj_values(raw: str) -> dict:
    """Parse: 'Event Name Actual X (Forecast Y, Previous Z)'"""
    result = {'title': raw, 'actual': None, 'forecast': None, 'previous': None}

    pattern = r'^(.+?)\s+Actual\s+([^\s(,]+(?:\s*%)?)\s*(?:\(Forecast\s+([^,)]+),\s*Previous\s+([^)]+)\))?'
    match = re.match(pattern, raw, re.IGNORECASE)

    if match:
        result['title'] = match.group(1).strip()
        result['actual'] = match.group(2).strip() if match.group(2) else None
        forecast = match.group(3).strip() if match.group(3) else None
        previous = match.group(4).strip() if match.group(4) else None
        result['forecast'] = None if forecast == '-' else forecast
        result['previous'] = None if previous == '-' else previous

    return result


def parse_pub_date(pub_date: str) -> datetime | None:
    cet = pytz.timezone('Europe/Paris')
    try:
        for fmt in ['%a, %d %b %Y %H:%M:%S %Z', '%a, %d %b %Y %H:%M:%S %z']:
            try:
                dt = datetime.strptime(pub_date, fmt)
                if dt.tzinfo is None:
                    dt = pytz.utc.localize(dt)
                return dt.astimezone(cet)
            except:
                continue
    except:
        pass
    return None


async def fetch_fj_rss() -> list:
    url = 'https://www.financialjuice.com/feed.ashx?xy=free'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    soup = BeautifulSoup(text, 'html.parser')
                    items = soup.find_all('item')

                    news = []
                    for item in items:
                        title_tag = item.find('title')
                        date_tag = item.find('pubDate')
                        guid_tag = item.find('guid')

                        if not title_tag:
                            continue

                        raw = title_tag.text.strip()
                        if raw.startswith('FinancialJuice:'):
                            raw = raw[15:].strip()

                        news.append({
                            'id': guid_tag.text.strip() if guid_tag else raw,
                            'raw': raw,
                            'pub_date': date_tag.text.strip() if date_tag else '',
                        })

                    print(f'✅ FJ RSS: {len(news)} items')
                    return news
    except Exception as e:
        print(f'❌ FJ RSS error: {e}')

    return []


def fmt_val(v):
    if v and str(v).strip() and v not in ['-', '']:
        return f'`{v}`'
    return '`N/A`'


async def fetch_weekly_events() -> list:
    cet = pytz.timezone('Europe/Paris')
    now = datetime.now(cet)
    monday = now - timedelta(days=now.weekday())
    friday = monday + timedelta(days=4)

    raw_news = await fetch_fj_rss()
    if not raw_news:
        return []

    week_events = []
    seen = set()

    for item in raw_news:
        raw = item.get('raw', '')

        # Doit contenir "Actual" pour être une annonce économique
        if 'actual' not in raw.lower():
            continue

        parsed = parse_fj_values(raw)
        title = parsed['title']

        currency = detect_currency(title)
        if not currency:
            continue

        # Parse date
        dt = parse_pub_date(item.get('pub_date', ''))
        if dt:
            if not (monday.date() <= dt.date() <= friday.date()):
                continue
            time_str = dt.strftime('%H:%M')
            day_name = dt.strftime('%A')
            date_display = dt.strftime('%A, %B %d')
        else:
            continue

        # Déduplication
        key = f'{currency}_{title}_{dt.date()}'
        if key in seen:
            continue
        seen.add(key)

        week_events.append({
            'id': item.get('id', ''),
            'currency': currency,
            'title': title,
            'actual': parsed['actual'],
            'forecast': parsed['forecast'],
            'previous': parsed['previous'],
            'high_impact': is_high_impact(title),
            '_time': time_str,
            '_day': day_name,
            '_date_display': date_display,
            '_dt': dt,
        })

    # Trie par heure
    week_events.sort(key=lambda x: x.get('_dt', datetime.min.replace(tzinfo=pytz.utc)))
    print(f'✅ Weekly events from FJ: {len(week_events)}')
    return week_events


def build_day_embed(day_name: str, day_events: list) -> discord.Embed:
    day_emoji = DAY_EMOJIS.get(day_name, '📆')
    date_display = day_events[0].get('_date_display', day_name)
    day_color = DAY_COLORS.get(day_name, 0x00d4a8)

    embed = discord.Embed(
        title=f'{day_emoji}  {date_display}',
        color=day_color
    )

    for event in day_events:
        currency = event.get('currency', '?')
        title = event.get('title', 'Unknown')
        time_str = event.get('_time', '—')
        forecast = event.get('forecast')
        previous = event.get('previous')
        actual = event.get('actual')
        high = event.get('high_impact', False)
        flag = CURRENCY_FLAGS.get(currency, '🌍')

        direction = ''
        if actual and forecast:
            try:
                def parse_num(v):
                    return float(str(v).replace('%', '').replace('K', '000').replace('M', '000000').replace('B', '000000000').strip())
                direction = ' 📈' if parse_num(actual) >= parse_num(forecast) else ' 📉'
            except:
                pass

        if actual:
            status = f'✅ **Actual:** {fmt_val(actual)}{direction}'
        elif forecast:
            status = f'📊 **Forecast:** {fmt_val(forecast)}'
        else:
            status = '⏳ Awaiting data...'

        big = '🔥 ' if high else ''

        embed.add_field(
            name=f'🔴  {flag} {currency}  ·  `{time_str} CET`',
            value=(
                f'{big}**{title}**\n'
                f'{status}  ·  📈 Previous {fmt_val(previous)}'
            ),
            inline=False
        )

    cet = pytz.timezone('Europe/Paris')
    now = datetime.now(cet)
    embed.set_footer(text=f'🔴 High Impact · MarketFlow Journal · Updated {now.strftime("%H:%M CET")}')
    return embed


async def post_weekly_calendar(channel: discord.TextChannel):
    global _calendar_messages, _last_events_data

    cet = pytz.timezone('Europe/Paris')
    now = datetime.now(cet)
    monday = now - timedelta(days=now.weekday())
    friday = monday + timedelta(days=4)

    try:
        await channel.purge(limit=30, check=lambda m: m.author.bot)
    except:
        pass

    _calendar_messages = {}
    _last_events_data = {}

    week_events = await fetch_weekly_events()

    header_embed = discord.Embed(color=0x00d4a8)
    header_embed.title = '📅 Economic Calendar — High Impact'

    if not week_events:
        header_embed.description = (
            f'**{monday.strftime("%B %d")} — {friday.strftime("%B %d, %Y")}**\n\n'
            f'No economic data published yet this week.\n'
            f'*Updates automatically as data is released.*'
        )
        header_embed.set_footer(text=f'Updated {now.strftime("%b %d at %H:%M CET")} • MarketFlow Journal')
        await channel.send(embed=header_embed)
        return

    currencies_week = sorted(set(e.get('currency', '') for e in week_events if e.get('currency')))
    currencies_display = '   '.join([f'{CURRENCY_FLAGS.get(c, "")} **{c}**' for c in currencies_week])
    big_events = [e for e in week_events if e.get('high_impact')]

    header_embed.description = (
        f'**{monday.strftime("%B %d")} — {friday.strftime("%B %d, %Y")}**\n'
        f'`{len(week_events)} releases` · 🔴 High Impact · 🕐 CET · 🔄 Live from FinancialJuice\n\n'
        f'{currencies_display}'
    )

    if big_events:
        big_titles = ', '.join(set(e.get('title', '') for e in big_events[:5]))
        header_embed.add_field(name='🔥 Major Events', value=big_titles, inline=False)

    header_embed.set_footer(text=f'Updated {now.strftime("%b %d at %H:%M CET")} • MarketFlow Journal')
    await channel.send(embed=header_embed)
    await asyncio.sleep(0.3)

    # Groupe par jour
    days_dict = {}
    for event in week_events:
        day = event.get('_day', 'Unknown')
        if day not in days_dict:
            days_dict[day] = []
        days_dict[day].append(event)

    _last_events_data = days_dict

    for day_name in DAY_ORDER:
        if day_name not in days_dict:
            continue
        day_events = sorted(days_dict[day_name], key=lambda x: x.get('_time', '00:00'))
        embed = build_day_embed(day_name, day_events)
        msg = await channel.send(embed=embed)
        _calendar_messages[day_name] = msg.id
        await asyncio.sleep(0.3)

    footer_embed = discord.Embed(color=0x0d1117)
    footer_embed.description = (
        '> ⚠️ **Risk Management** — Always protect your capital during high-impact releases.\n'
        '> *Content is for educational purposes only — not financial advice.*\n'
        '> 🔥 = Major event · Source: FinancialJuice'
    )
    footer_embed.set_footer(text=f'MarketFlow Journal · {now.strftime("%B %d, %Y")}')
    await channel.send(footer_embed)
    print(f'✅ Calendrier posté avec {len(_calendar_messages)} jours')


async def update_calendar_data(channel: discord.TextChannel):
    global _calendar_messages, _last_events_data

    if not _calendar_messages:
        return

    week_events = await fetch_weekly_events()
    if not week_events:
        return

    new_days = {}
    for event in week_events:
        day = event.get('_day', 'Unknown')
        if day not in new_days:
            new_days[day] = []
        new_days[day].append(event)

    updated = 0
    for day_name, msg_id in _calendar_messages.items():
        if day_name not in new_days:
            continue

        new_events = sorted(new_days[day_name], key=lambda x: x.get('_time', '00:00'))
        old_events = _last_events_data.get(day_name, [])

        changed = len(new_events) != len(old_events)
        if not changed:
            for new_e, old_e in zip(new_events, old_events):
                if new_e.get('actual') != old_e.get('actual'):
                    changed = True
                    break

        if changed:
            try:
                msg = await channel.fetch_message(msg_id)
                new_embed = build_day_embed(day_name, new_events)
                await msg.edit(embed=new_embed)
                updated += 1
                print(f'🔄 Calendar updated: {day_name}')
            except Exception as e:
                print(f'❌ Update error {day_name}: {e}')

    if updated > 0:
        print(f'✅ {updated} calendar message(s) updated')

    _last_events_data = new_days


class Calendar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.calendar_task = None
        self.update_task = None

    @commands.Cog.listener()
    async def on_ready(self):
        print('✅ Cog Calendar prêt')
        if self.calendar_task is None or self.calendar_task.done():
            self.calendar_task = asyncio.ensure_future(self.weekly_calendar_loop())
        if self.update_task is None or self.update_task.done():
            self.update_task = asyncio.ensure_future(self.auto_update_loop())

    async def weekly_calendar_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                cet = pytz.timezone('Europe/Paris')
                now = datetime.now(cet)

                days_until_monday = (7 - now.weekday()) % 7
                if days_until_monday == 0 and now.hour >= 8:
                    days_until_monday = 7

                next_monday = now + timedelta(days=days_until_monday)
                next_monday_8am = next_monday.replace(hour=8, minute=0, second=0, microsecond=0)

                wait_seconds = (next_monday_8am - now).total_seconds()
                hours = int(wait_seconds // 3600)
                minutes = int((wait_seconds % 3600) // 60)
                print(f'📅 Prochain calendrier dans {hours}h{minutes}m (lundi 08h00 CET)')

                await asyncio.sleep(wait_seconds)

                guild = self.bot.get_guild(int(os.getenv('GUILD_ID')))
                if guild:
                    channel_id = int(os.getenv('CALENDAR_CHANNEL_ID', 0))
                    channel = guild.get_channel(channel_id)
                    if channel:
                        await post_weekly_calendar(channel)
                        print('✅ Calendrier posté automatiquement')

            except Exception as e:
                print(f'❌ Calendar loop error: {e}')
                await asyncio.sleep(60)

    async def auto_update_loop(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(60)

        while not self.bot.is_closed():
            try:
                guild = self.bot.get_guild(int(os.getenv('GUILD_ID')))
                if guild and _calendar_messages:
                    channel_id = int(os.getenv('CALENDAR_CHANNEL_ID', 0))
                    channel = guild.get_channel(channel_id)
                    if channel:
                        await update_calendar_data(channel)
                await asyncio.sleep(120)
            except Exception as e:
                print(f'❌ Auto-update error: {e}')
                await asyncio.sleep(60)

    @app_commands.command(name='calendar', description='Poste le calendrier économique maintenant')
    async def calendar(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            await interaction.response.send_message('❌ Permission denied.', ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        channel_id = int(os.getenv('CALENDAR_CHANNEL_ID', 0))
        channel = interaction.guild.get_channel(channel_id)

        if not channel:
            await interaction.followup.send('❌ Calendar channel introuvable.', ephemeral=True)
            return

        await post_weekly_calendar(channel)
        await interaction.followup.send('✅ Calendrier posté !', ephemeral=True)

    @app_commands.command(name='post_event', description='Poste un événement économique manuellement')
    async def post_event(
        self,
        interaction: discord.Interaction,
        event_name: str,
        currency: str,
        date: str,
        time_cet: str,
        impact: str = 'High'
    ):
        if not is_staff(interaction.user):
            await interaction.response.send_message('❌ Permission denied.', ephemeral=True)
            return

        impact_colors = {'high': 0xef4444, 'medium': 0xf59e0b, 'low': 0x6b7280}
        impact_emojis = {'high': '🔴', 'medium': '🟡', 'low': '⚪'}
        color = impact_colors.get(impact.lower(), 0x00d4a8)
        emoji = impact_emojis.get(impact.lower(), '📌')
        flag = CURRENCY_FLAGS.get(currency.upper(), '🌍')

        embed = discord.Embed(title=f'{emoji} {event_name}', color=color)
        embed.add_field(name='Currency', value=f'{flag} `{currency.upper()}`', inline=True)
        embed.add_field(name='Date', value=date, inline=True)
        embed.add_field(name='Time (CET)', value=time_cet, inline=True)
        embed.add_field(name='Impact', value=f'{emoji} **{impact.upper()}**', inline=True)
        embed.set_footer(text='MarketFlow Journal — Economic Calendar')
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Calendar(bot))