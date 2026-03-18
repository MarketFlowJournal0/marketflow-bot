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
                print(f'📡 FCS API status: {resp.status}')
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    raw_events = data.get('response', [])
                    print(f'📡 FCS API total events: {len(raw_events)}')

                    for event in raw_events:
                        currency = event.get('currency', '')
                        if currency not in FOREX_CURRENCIES:
                            continue
                        if str(event.get('importance', '')) != '2':
                            continue

                        events.append({
                            'currency': currency,
                            'title': event.get('title', 'Unknown'),
                            'date': event.get('date', ''),
                            'time': event.get('time', ''),
                            'forecast': event.get('forecast') or '—',
                            'previous': event.get('previous') or '—',
                            'actual': event.get('actual') or None,
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
        time_str = event.get('time', '')
        if not date_str:
            return None

        if time_str and time_str not in ['', 'Tentative', 'All Day']:
            for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%m/%d/%Y %H:%M']:
                try:
                    dt = datetime.strptime(f'{date_str} {time_str}', fmt)
                    return pytz.utc.localize(dt).astimezone(cet)
                except:
                    continue

        for fmt in ['%Y-%m-%d', '%m/%d/%Y']:
            try:
                dt = datetime.strptime(date_str[:10], fmt)
                return pytz.utc.localize(dt).astimezone(cet)
            except:
                continue
    except:
        pass
    return None


async def post_weekly_calendar(channel: discord.TextChannel):
    cet = pytz.timezone('Europe/Paris')
    now = datetime.now(cet)
    monday = now - timedelta(days=now.weekday())
    friday = monday + timedelta(days=4)

    try:
        await channel.purge(limit=30, check=lambda m: m.author.bot)
    except:
        pass

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
            for fmt in ['%Y-%m-%d', '%m/%d/%Y']:
                try:
                    d = datetime.strptime(date_str[:10], fmt)
                    if monday.date() <= d.date() <= friday.date():
                        event['_day'] = d.strftime('%A')
                        event['_time'] = event.get('time', 'TBD') or 'TBD'
                        event['_date_display'] = d.strftime('%A, %B %d')
                        week_events.append(event)
                    break
                except:
                    continue

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
        f'`{len(week_events)} events` · 🔴 High Impact Only · 🕐 CET (Paris)\n\n'
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

    for day_name in DAY_ORDER:
        if day_name not in days_dict:
            continue

        day_events = sorted(days_dict[day_name], key=lambda x: x.get('_time', '00:00'))
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
            forecast = event.get('forecast') or '—'
            previous = event.get('previous') or '—'
            actual = event.get('actual')
            flag = CURRENCY_FLAGS.get(currency, '🌍')

            direction = ''
            if actual and forecast and forecast != '—':
                try:
                    def parse_val(v):
                        return float(str(v).replace('%', '').replace('K', '000').replace('M', '000000').replace('B', '000000000').strip())
                    direction = ' 📈' if parse_val(actual) >= parse_val(forecast) else ' 📉'
                except:
                    pass

            actual_str = f'\n✅ **Actual:** `{actual}`{direction}' if actual and str(actual).strip() else ''
            forecast_display = f'`{forecast}`' if forecast != '—' else '`N/A`'
            previous_display = f'`{previous}`' if previous != '—' else '`N/A`'

            embed.add_field(
                name=f'🔴  {flag} {currency}  ·  `{time_str} CET`',
                value=(
                    f'**{title}**\n'
                    f'📊 Forecast {forecast_display}  ·  📈 Previous {previous_display}'
                    f'{actual_str}'
                ),
                inline=False
            )

        embed.set_footer(text=f'🔴 High Impact · MarketFlow Journal · {date_display}')
        await channel.send(embed=embed)
        await asyncio.sleep(0.3)

    # FOOTER
    footer_embed = discord.Embed(color=0x0d1117)
    footer_embed.description = (
        '> ⚠️ **Risk Management** — Always protect your capital during high-impact releases.\n'
        '> *Content is for educational purposes only and does not constitute financial advice.*'
    )
    footer_embed.set_footer(text=f'MarketFlow Journal — Trading Journal · {now.strftime("%B %d, %Y")}')
    await channel.send(embed=footer_embed)


class Calendar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.calendar_task = None

    @commands.Cog.listener()
    async def on_ready(self):
        print('✅ Cog Calendar prêt')
        if self.calendar_task is None or self.calendar_task.done():
            self.calendar_task = asyncio.ensure_future(self.weekly_calendar_loop())

    async def weekly_calendar_loop(self):
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