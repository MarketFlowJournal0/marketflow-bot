import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
import pytz

def is_owner(user_id: int) -> bool:
    return user_id == int(os.getenv('OWNER_ID', 0))

def is_staff(member: discord.Member) -> bool:
    return is_owner(member.id) or any(r.name == 'MFJ Teams' for r in member.roles)

FOREX_CURRENCIES = ['USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'CHF', 'NZD']

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

# Cache des messages postés pour mise à jour
# Format: {day_name: message_id}
_calendar_messages = {}
_last_events_data = {}


async def fetch_calendar_events() -> list:
    api_key = os.getenv('FCSAPI_KEY', '')
    if not api_key:
        print('❌ FCSAPI_KEY manquant dans .env')
        return []

    cet = pytz.timezone('Europe/Paris')
    now = datetime.now(cet)
    monday = now - timedelta(days=now.weekday())
    friday = monday + timedelta(days=4)

    url = 'https://fcsapi.com/api-v3/forex/economy_cal'
    params = {
        'access_key': api_key,
        'from': monday.strftime('%Y-%m-%d'),
        'to': friday.strftime('%Y-%m-%d'),
    }

    events = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    raw_events = data.get('response', [])

                    for event in raw_events:
                        currency = event.get('currency', '')
                        if currency not in FOREX_CURRENCIES:
                            continue
                        if str(event.get('importance', '')) != '2':
                            continue

                        events.append({
                            'id': event.get('id', ''),
                            'currency': currency,
                            'title': event.get('title', 'Unknown'),
                            'date': event.get('date', ''),
                            'forecast': event.get('forecast') or None,
                            'previous': event.get('previous') or None,
                            'actual': event.get('actual') or None,
                            'unit': event.get('unit', ''),
                            'period': event.get('period', ''),
                        })

                    print(f'✅ FCS API: {len(events)} high-impact events fetched')
                    return events
                else:
                    print(f'❌ FCS API error {resp.status}')
    except Exception as e:
        print(f'❌ FCS API fetch error: {e}')

    return []


def parse_event_dt(event: dict) -> datetime | None:
    cet = pytz.timezone('Europe/Paris')
    try:
        date_str = event.get('date', '')
        if not date_str:
            return None
        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d']:
            try:
                dt = datetime.strptime(date_str, fmt)
                dt_utc = pytz.utc.localize(dt)
                return dt_utc.astimezone(cet)
            except:
                continue
    except:
        pass
    return None


def build_day_embed(day_name: str, day_events: list) -> discord.Embed:
    """Construit l'embed pour un jour donné"""
    day_emoji = DAY_EMOJIS.get(day_name, '📆')
    date_display = day_events[0].get('_date_display', day_name)
    day_color = DAY_COLORS.get(day_name, 0x00d4a8)

    embed = discord.Embed(
        title=f'{day_emoji}  {date_display}',
        color=day_color
    )

    for event in day_events:
        currency = event.get('currency', '?')
        title = event.get('title', 'Unknown Event')
        time_str = event.get('_time', '—')
        forecast = event.get('forecast')
        previous = event.get('previous')
        actual = event.get('actual')
        unit = event.get('unit', '')
        period = event.get('period', '')
        flag = CURRENCY_FLAGS.get(currency, '🌍')

        def fmt_val(v, u=''):
            if v and str(v).strip():
                return f'`{v}{u}`' if u else f'`{v}`'
            return '`N/A`'

        # Direction si actual disponible
        direction = ''
        if actual and forecast:
            try:
                def parse_val(v):
                    return float(str(v).replace('%', '').replace('K', '000').replace('M', '000000').replace('B', '000000000').strip())
                direction = ' 📈' if parse_val(actual) >= parse_val(forecast) else ' 📉'
            except:
                pass

        # Status de l'event
        if actual and str(actual).strip():
            status = f'✅ **Actual:** {fmt_val(actual, unit)}{direction}'
        elif forecast and str(forecast).strip():
            status = f'📊 **Forecast:** {fmt_val(forecast, unit)}'
        else:
            status = '⏳ Awaiting data...'

        period_str = f' · `{period}`' if period else ''

        embed.add_field(
            name=f'🔴  {flag} {currency}  ·  `{time_str} CET`{period_str}',
            value=(
                f'**{title}**\n'
                f'{status}  ·  📈 Previous {fmt_val(previous, unit)}'
            ),
            inline=False
        )

    embed.set_footer(text=f'🔴 High Impact · MarketFlow Journal · Updated {datetime.now(pytz.timezone("Europe/Paris")).strftime("%H:%M CET")}')
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

    events = await fetch_calendar_events()

    week_events = []
    for event in events:
        dt = parse_event_dt(event)
        if dt and monday.date() <= dt.date() <= friday.date():
            event['_dt'] = dt
            event['_day'] = dt.strftime('%A')
            event['_time'] = dt.strftime('%H:%M')
            event['_date_display'] = dt.strftime('%A, %B %d')
            week_events.append(event)
        elif not dt:
            date_str = event.get('date', '')
            try:
                d = datetime.strptime(date_str[:10], '%Y-%m-%d')
                if monday.date() <= d.date() <= friday.date():
                    event['_day'] = d.strftime('%A')
                    event['_time'] = 'TBD'
                    event['_date_display'] = d.strftime('%A, %B %d')
                    week_events.append(event)
            except:
                pass

    # HEADER
    header_embed = discord.Embed(color=0x00d4a8)

    if not week_events:
        header_embed.title = '📅 Economic Calendar — High Impact'
        header_embed.description = (
            f'**{monday.strftime("%B %d")} — {friday.strftime("%B %d, %Y")}**\n\n'
            f'No major economic releases scheduled this week.'
        )
        header_embed.set_footer(text=f'Updated {now.strftime("%b %d at %H:%M CET")} • MarketFlow Journal')
        await channel.send(embed=header_embed)
        return

    currencies_week = sorted(set(e.get('currency', '') for e in week_events if e.get('currency')))
    currencies_display = '   '.join([f'{CURRENCY_FLAGS.get(c, "")} **{c}**' for c in currencies_week])

    header_embed.title = '📅 Economic Calendar — High Impact'
    header_embed.description = (
        f'**{monday.strftime("%B %d")} — {friday.strftime("%B %d, %Y")}**\n'
        f'`{len(week_events)} events` · 🔴 High Impact Only · 🕐 CET (Paris)\n'
        f'🔄 *Auto-updated every 5 minutes*\n\n'
        f'{currencies_display}'
    )
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

    # Stocke les events pour mise à jour
    _last_events_data = days_dict

    for day_name in DAY_ORDER:
        if day_name not in days_dict:
            continue

        day_events = sorted(days_dict[day_name], key=lambda x: x.get('_time', '00:00'))
        embed = build_day_embed(day_name, day_events)
        msg = await channel.send(embed=embed)
        _calendar_messages[day_name] = msg.id
        await asyncio.sleep(0.3)

    # FOOTER
    footer_embed = discord.Embed(color=0x0d1117)
    footer_embed.description = (
        '> ⚠️ **Risk Management** — Always protect your capital during high-impact releases.\n'
        '> *Content is for educational purposes only and does not constitute financial advice.*'
    )
    footer_embed.set_footer(text=f'MarketFlow Journal — Trading Journal · {now.strftime("%B %d, %Y")}')
    await channel.send(footer_embed)

    print(f'✅ Calendrier posté avec {len(_calendar_messages)} jours')


async def update_calendar_data(channel: discord.TextChannel):
    """Met à jour les messages du calendrier avec les nouvelles données"""
    global _calendar_messages, _last_events_data

    if not _calendar_messages:
        return

    events = await fetch_calendar_events()
    if not events:
        return

    cet = pytz.timezone('Europe/Paris')
    now = datetime.now(cet)
    monday = now - timedelta(days=now.weekday())
    friday = monday + timedelta(days=4)

    # Rebuild week events
    week_events = []
    for event in events:
        dt = parse_event_dt(event)
        if dt and monday.date() <= dt.date() <= friday.date():
            event['_dt'] = dt
            event['_day'] = dt.strftime('%A')
            event['_time'] = dt.strftime('%H:%M')
            event['_date_display'] = dt.strftime('%A, %B %d')
            week_events.append(event)

    if not week_events:
        return

    # Groupe par jour
    new_days = {}
    for event in week_events:
        day = event.get('_day', 'Unknown')
        if day not in new_days:
            new_days[day] = []
        new_days[day].append(event)

    # Compare et met à jour seulement si changement
    updated = 0
    for day_name, msg_id in _calendar_messages.items():
        if day_name not in new_days:
            continue

        new_events = sorted(new_days[day_name], key=lambda x: x.get('_time', '00:00'))
        old_events = sorted(_last_events_data.get(day_name, []), key=lambda x: x.get('_time', '00:00'))

        # Vérifie si les données ont changé
        changed = False
        for new_e in new_events:
            event_id = new_e.get('id', '')
            for old_e in old_events:
                if old_e.get('id', '') == event_id:
                    if (new_e.get('actual') != old_e.get('actual') or
                            new_e.get('forecast') != old_e.get('forecast')):
                        changed = True
                        break

        if changed:
            try:
                msg = await channel.fetch_message(msg_id)
                new_embed = build_day_embed(day_name, new_events)
                await msg.edit(embed=new_embed)
                updated += 1
                print(f'🔄 Updated calendar: {day_name}')
            except Exception as e:
                print(f'❌ Update error for {day_name}: {e}')

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
        """Poste chaque lundi à 00h00 CET"""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                cet = pytz.timezone('Europe/Paris')
                now = datetime.now(cet)

                days_until_monday = (7 - now.weekday()) % 7
                if days_until_monday == 0 and now.hour >= 0:
                    days_until_monday = 7

                next_monday = now + timedelta(days=days_until_monday)
                next_monday_midnight = next_monday.replace(hour=0, minute=0, second=0, microsecond=0)

                wait_seconds = (next_monday_midnight - now).total_seconds()
                hours = int(wait_seconds // 3600)
                minutes = int((wait_seconds % 3600) // 60)
                print(f'📅 Prochain calendrier dans {hours}h{minutes}m (lundi 00h00 CET)')

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
        """Met à jour le calendrier toutes les 5 minutes"""
        await self.bot.wait_until_ready()
        await asyncio.sleep(30)  # Attend 30s après le démarrage

        while not self.bot.is_closed():
            try:
                guild = self.bot.get_guild(int(os.getenv('GUILD_ID')))
                if guild and _calendar_messages:
                    channel_id = int(os.getenv('CALENDAR_CHANNEL_ID', 0))
                    channel = guild.get_channel(channel_id)
                    if channel:
                        await update_calendar_data(channel)

                await asyncio.sleep(300)  # 5 minutes

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