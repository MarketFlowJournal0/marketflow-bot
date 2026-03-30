import discord
from discord.ext import commands
import os
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
import re

_last_news_ids = set()
_news_channel = None

FOREX_KEYWORDS = [
    'fed', 'fomc', 'federal reserve', 'powell',
    'ecb', 'lagarde', 'european central bank',
    'boe', 'bank of england', 'bailey',
    'boj', 'bank of japan', 'ueda',
    'boc', 'bank of canada',
    'rba', 'reserve bank of australia',
    'snb', 'swiss national bank',
    'interest rate', 'rate decision', 'rate hike', 'rate cut',
    'inflation', 'cpi', 'pce',
    'nfp', 'non-farm', 'nonfarm', 'payroll',
    'gdp', 'unemployment', 'jobless',
    'pmi', 'ism', 'retail sales',
    'fomc minutes', 'monetary policy',
    'usd', 'eur', 'gbp', 'jpy', 'cad', 'aud', 'chf', 'nzd',
    'dollar', 'euro', 'pound', 'yen',
    'tariff', 'trade war', 'sanctions',
    'recession', 'gdp growth',
]

HIGH_IMPACT_KEYWORDS = [
    'fed', 'fomc', 'rate decision', 'interest rate',
    'nfp', 'non-farm', 'nonfarm',
    'cpi', 'inflation',
    'ecb', 'boe', 'boj',
    'gdp',
    'emergency', 'crisis', 'crash', 'collapse',
    'rate hike', 'rate cut',
]

CURRENCY_FLAGS = {
    'USD': '🇺🇸', 'EUR': '🇪🇺', 'GBP': '🇬🇧',
    'JPY': '🇯🇵', 'CAD': '🇨🇦', 'AUD': '🇦🇺',
    'CHF': '🇨🇭', 'NZD': '🇳🇿'
}

CURRENCY_MAP = {
    'usd': 'USD', 'dollar': 'USD', 'fed': 'USD', 'fomc': 'USD',
    'federal reserve': 'USD', 'powell': 'USD',
    'eur': 'EUR', 'euro': 'EUR', 'ecb': 'EUR', 'lagarde': 'EUR',
    'gbp': 'GBP', 'pound': 'GBP', 'boe': 'GBP', 'bailey': 'GBP',
    'jpy': 'JPY', 'yen': 'JPY', 'boj': 'JPY', 'ueda': 'JPY',
    'cad': 'CAD', 'boc': 'CAD',
    'aud': 'AUD', 'rba': 'AUD',
    'chf': 'CHF', 'snb': 'CHF',
    'nzd': 'NZD',
}


def detect_currency(text: str) -> str:
    text_lower = text.lower()
    for keyword, currency in CURRENCY_MAP.items():
        if keyword in text_lower:
            return currency
    return ''


def is_high_impact(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in HIGH_IMPACT_KEYWORDS)


def is_forex_relevant(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in FOREX_KEYWORDS)


async def fetch_financialjuice_news() -> list:
    """Scrape FinancialJuice pour les dernières news"""
    url = 'https://www.financialjuice.com/feed.ashx?xy=free'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json, text/plain, */*',
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    return data if isinstance(data, list) else []
    except Exception as e:
        pass

    # Fallback — scrape la page principale
    try:
        async with aiohttp.ClientSession() as session:
            headers2 = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
            async with session.get(
                'https://www.financialjuice.com/',
                headers=headers2,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    news_items = []

                    # Cherche les news dans la page
                    for item in soup.select('.news-item, .headline, [class*="news"], [class*="headline"]')[:20]:
                        text = item.get_text(strip=True)
                        if text and len(text) > 20:
                            news_items.append({
                                'id': hash(text),
                                'text': text,
                                'time': datetime.now(pytz.timezone('Europe/Paris')).strftime('%H:%M')
                            })

                    return news_items
    except Exception as e:
        print(f'❌ FinancialJuice scrape error: {e}')

    return []


def build_news_embed(news_item: dict, currency: str, high_impact: bool) -> discord.Embed:
    cet = pytz.timezone('Europe/Paris')
    now = datetime.now(cet)

    text = news_item.get('text', news_item.get('title', news_item.get('headline', 'Unknown')))
    time_str = news_item.get('time', now.strftime('%H:%M'))

    color = 0xef4444 if high_impact else 0xf59e0b
    flag = CURRENCY_FLAGS.get(currency, '🌍')
    impact_emoji = '🔴' if high_impact else '🟡'
    impact_label = '**HIGH IMPACT**' if high_impact else 'Medium Impact'

    embed = discord.Embed(
        description=f'**{text}**',
        color=color
    )

    embed.set_author(name=f'{impact_emoji} {impact_label} — FinancialJuice')

    if currency:
        embed.add_field(name='Currency', value=f'{flag} **{currency}**', inline=True)
    embed.add_field(name='Time', value=f'`{time_str} CET`', inline=True)

    embed.set_footer(text=f'MarketFlow Journal — News Alerts · {now.strftime("%b %d at %H:%M CET")}')
    return embed


class FinancialJuice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.news_task = None

    @commands.Cog.listener()
    async def on_ready(self):
        global _news_channel
        print('✅ Cog FinancialJuice prêt')

        guild = self.bot.get_guild(int(os.getenv('GUILD_ID')))
        if not guild:
            return

        news_channel_id = int(os.getenv('NEWS_ALERTS_CHANNEL_ID', 0))
        _news_channel = guild.get_channel(news_channel_id)

        if _news_channel:
            print(f'✅ News alerts channel: {_news_channel.name}')
        else:
            print('❌ NEWS_ALERTS_CHANNEL_ID introuvable')
            return

        if self.news_task is None or self.news_task.done():
            self.news_task = asyncio.ensure_future(self.news_loop())

    async def news_loop(self):
        """Vérifie les nouvelles toutes les 2 minutes"""
        await self.bot.wait_until_ready()
        await asyncio.sleep(30)

        print('✅ FinancialJuice news loop démarré')

        while not self.bot.is_closed():
            try:
                await self.check_news()
                await asyncio.sleep(120)  # 2 minutes
            except Exception as e:
                print(f'❌ News loop error: {e}')
                await asyncio.sleep(60)

    async def check_news(self):
        global _last_news_ids, _news_channel

        if not _news_channel:
            return

        news = await fetch_financialjuice_news()
        if not news:
            return

        new_items = []
        for item in news:
            item_id = str(item.get('id', item.get('ID', hash(str(item)))))

            if item_id in _last_news_ids:
                continue

            text = item.get('text', item.get('title', item.get('headline', item.get('Text', ''))))
            if not text:
                continue

            if not is_forex_relevant(text):
                continue

            new_items.append((item_id, item, text))

        # Limite à 5 nouvelles par cycle pour éviter le spam
        for item_id, item, text in new_items[:5]:
            _last_news_ids.add(item_id)

            currency = detect_currency(text)
            high = is_high_impact(text)

            embed = build_news_embed(item, currency, high)
            try:
                await _news_channel.send(embed=embed)
                await asyncio.sleep(1)
            except Exception as e:
                print(f'❌ Error sending news: {e}')

        # Garde seulement les 500 derniers IDs en mémoire
        if len(_last_news_ids) > 500:
            _last_news_ids = set(list(_last_news_ids)[-500:])


async def setup(bot):
    await bot.add_cog(FinancialJuice(bot))