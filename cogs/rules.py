import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio

_log_channel = None

def is_owner(user_id: int) -> bool:
    return user_id == int(os.getenv('OWNER_ID', 0))

def is_staff(member: discord.Member) -> bool:
    return is_owner(member.id) or any(r.name == 'MFJ Teams' for r in member.roles)

class AcceptRulesView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label='✅ I have read and accept the rules',
        style=discord.ButtonStyle.success,
        custom_id='accept_rules'
    )
    async def accept_rules(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user

        membre_role = discord.utils.get(guild.roles, name='MFJ Membre')
        verif_role = discord.utils.get(guild.roles, name='MFJ Verification')

        if membre_role and membre_role in member.roles:
            await interaction.response.send_message(
                '✅ You are already a full member!',
                ephemeral=True
            )
            return

        embed_confirm = discord.Embed(
            title='🎉 Welcome to MarketFlow Journal!',
            description=(
                f'Hey **{member.display_name}**,\n\n'
                'You now have **full access** to the server.\n\n'
                '📊 Start journaling your trades and level up your trading game!\n\n'
                '**Happy trading! 📈**'
            ),
            color=0x00d4a8
        )
        embed_confirm.set_footer(text='MarketFlow Journal — Trading Journal')
        await interaction.response.send_message(embed=embed_confirm, ephemeral=True)

        async def background():
            try:
                if verif_role and verif_role in member.roles:
                    await member.remove_roles(verif_role)
                if membre_role:
                    await member.add_roles(membre_role)

                if _log_channel:
                    embed_log = discord.Embed(title='✅ New Member', color=0x00d4a8)
                    embed_log.add_field(name='Member', value=f'{member.mention} (`{member.id}`)', inline=False)
                    embed_log.add_field(name='Status', value='Rules accepted — Full access granted', inline=False)
                    embed_log.set_footer(text='MarketFlow Journal — Verification System')
                    await _log_channel.send(embed=embed_log)

                try:
                    embed_dm = discord.Embed(
                        title='👋 Welcome to MarketFlow Journal!',
                        description=(
                            f'Hey **{member.display_name}**,\n\n'
                            'You now have full access to the **MarketFlow Journal** Discord.\n\n'
                            '📊 **MarketFlow Journal** is the most advanced trading journal built for serious traders.\n\n'
                            'Happy trading! 📈'
                        ),
                        color=0x00d4a8
                    )
                    embed_dm.set_footer(text='MarketFlow Journal — Trading Journal')
                    await member.send(embed=embed_dm)
                except:
                    pass

            except Exception as e:
                print(f'❌ Rules background error: {e}')

        asyncio.ensure_future(background())


class Rules(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(AcceptRulesView())

    @commands.Cog.listener()
    async def on_ready(self):
        global _log_channel
        print('✅ Cog Rules prêt')

        guild = self.bot.get_guild(int(os.getenv('GUILD_ID')))
        if not guild:
            return

        log_channel_id = int(os.getenv('LOG_CHANNEL_ID', 0))
        _log_channel = guild.get_channel(log_channel_id)

        rules_channel_id = int(os.getenv('RULES_CHANNEL_ID', 0))
        rules_channel = guild.get_channel(rules_channel_id)
        if not rules_channel:
            print('❌ Rules channel introuvable — vérifie RULES_CHANNEL_ID dans .env')
            return

        messages = [msg async for msg in rules_channel.history(limit=10)]
        bot_messages = [m for m in messages if m.author == self.bot.user]

        if len(bot_messages) == 1:
            print('✅ Message des règles déjà présent')
            return

        await rules_channel.purge(limit=100, check=lambda m: m.author == self.bot.user)
        await self._post_rules(rules_channel)
        print('✅ Règles postées')

    async def _post_rules(self, channel):
        embed = discord.Embed(
            title='📜 MarketFlow Journal — Community Rules',
            description='Welcome to **MarketFlow Journal**. Please read and accept the rules below to gain full access to the server.',
            color=0x00d4a8
        )
        embed.add_field(name='01 — Be Kind', value='Treat every member with kindness and respect. No personal attacks or harassment of any kind.', inline=False)
        embed.add_field(name='02 — No Spam', value='No spam, flooding or repetitive messages. Keep the chat clean.', inline=False)
        embed.add_field(name='03 — No Solicitation', value='No promotion, advertising, solicitation or business use of the chat.', inline=False)
        embed.add_field(name='04 — No Signal Services', value='No signal selling, account management or EA promotion of any kind.', inline=False)
        embed.add_field(name='05 — Stay Professional', value='No profanity, threats, defamation or sexual, religious and racial content.', inline=False)
        embed.add_field(name='06 — Respect Opinions', value='Do not dominate conversations. Maintain respect for all members and their opinions.', inline=False)
        embed.add_field(name='07 — No Competition', value='Do not promote or advertise competing platforms or services.', inline=False)
        embed.add_field(name='08 — Trading Disclaimer', value='All shared content is personal opinion only. Nothing posted here constitutes financial advice.', inline=False)
        embed.add_field(name='09 — Staff Decisions', value='Respect staff decisions at all times. Disputes must be handled via support ticket only.', inline=False)
        embed.add_field(name='10 — Terms & Conditions', value='By accepting, you agree to MarketFlow Journal\'s Terms & Conditions.', inline=False)
        embed.set_footer(text='⚠️ Rule violations may result in a permanent ban • MarketFlow Journal')
        await channel.send(embed=embed, view=AcceptRulesView())

    @app_commands.command(name='setup_rules', description='Poste les règles avec bouton d\'acceptation')
    async def setup_rules(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                '❌ You do not have permission to use this command.',
                ephemeral=True
            )
            return
        await interaction.response.send_message('⏳ Setup en cours...', ephemeral=True)
        await interaction.channel.purge(limit=100, check=lambda m: m.author == self.bot.user)
        await self._post_rules(interaction.channel)


async def setup(bot):
    await bot.add_cog(Rules(bot))