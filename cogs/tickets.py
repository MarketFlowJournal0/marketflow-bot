import discord
from discord.ext import commands
from discord import app_commands
import os
import asyncio
from datetime import datetime
import pytz

def is_owner(user_id: int) -> bool:
    return user_id == int(os.getenv('OWNER_ID', 0))

def is_staff(member: discord.Member) -> bool:
    return is_owner(member.id) or any(r.name == 'MFJ Teams' for r in member.roles)

_log_channel = None


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label='🛠️ Support',
        style=discord.ButtonStyle.secondary,
        custom_id='ticket_support'
    )
    async def support(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title='🛠️ MarketFlow Journal — Support',
            description=(
                'Need help? Our support team is available directly on the platform.\n\n'
                '🔗 **[Open a Support Ticket → marketflowjournal.com/support](https://marketflowjournal.com/support)**\n\n'
                'You can also reach us via email or live chat on the website.\n'
                'Average response time: **< 24 hours**'
            ),
            color=0x00d4a8
        )
        embed.set_footer(text='MarketFlow Journal — Support Team')
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label='💡 Submit an Idea',
        style=discord.ButtonStyle.success,
        custom_id='ticket_idea'
    )
    async def idea(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user

        # Vérifie si le membre a déjà un ticket ouvert
        existing = discord.utils.get(
            guild.text_channels,
            name=f'idea-{member.name.lower().replace(" ", "-")}'
        )
        if existing:
            await interaction.response.send_message(
                f'❌ You already have an open idea ticket: {existing.mention}',
                ephemeral=True
            )
            return

        # Répond immédiatement
        await interaction.response.send_message(
            '⏳ Creating your idea ticket...',
            ephemeral=True
        )

        # Permissions
        staff_role = discord.utils.get(guild.roles, name='MFJ Teams')
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                attach_files=True,
                embed_links=True
            ),
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                manage_messages=True
            )

        # Cherche catégorie SUPPORT
        category = discord.utils.get(guild.categories, name='🎫 SUPPORT')

        # Crée le salon
        channel = await guild.create_text_channel(
            name=f'idea-{member.name.lower().replace(" ", "-")}',
            category=category,
            overwrites=overwrites,
            topic=f'Idea ticket — {member} ({member.id})'
        )

        # Message d'ouverture
        embed_open = discord.Embed(
            title='💡 Idea Ticket — MarketFlow Journal',
            description=(
                f'Hey {member.mention} 👋\n\n'
                'Welcome to your **idea ticket**!\n\n'
                '📝 **Share your idea below** — be as detailed as possible:\n'
                '- What feature or improvement are you suggesting?\n'
                '- Why would it be useful for traders?\n'
                '- Any examples or references?\n\n'
                'Our team will review your idea and get back to you here.'
            ),
            color=0x00d4a8
        )
        embed_open.set_footer(text=f'MarketFlow Journal — Idea #{channel.name}')

        await channel.send(
            embed=embed_open,
            view=CloseTicketView(member_id=member.id)
        )

        # Log
        if _log_channel:
            embed_log = discord.Embed(title='💡 New Idea Ticket', color=0x00d4a8)
            embed_log.add_field(name='Member', value=f'{member.mention} (`{member.id}`)', inline=False)
            embed_log.add_field(name='Channel', value=channel.mention, inline=False)
            embed_log.set_footer(text='MarketFlow Journal — Ticket System')
            await _log_channel.send(embed=embed_log)

        await interaction.edit_original_response(
            content=f'✅ Your idea ticket has been created: {channel.mention}'
        )


class CloseTicketView(discord.ui.View):
    def __init__(self, member_id: int = None):
        super().__init__(timeout=None)
        self.member_id = member_id

    @discord.ui.button(
        label='🔒 Close Ticket',
        style=discord.ButtonStyle.danger,
        custom_id='close_ticket'
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_staff(interaction.user):
            await interaction.response.send_message(
                '❌ Only staff can close tickets.',
                ephemeral=True
            )
            return

        channel = interaction.channel
        guild = interaction.guild

        await interaction.response.send_message('⏳ Closing ticket...', ephemeral=True)

        # Récupère les messages du ticket pour le transcript
        messages = []
        async for msg in channel.history(limit=200, oldest_first=True):
            if not msg.author.bot:
                cet = pytz.timezone('Europe/Paris')
                dt = msg.created_at.astimezone(cet)
                messages.append(f'[{dt.strftime("%b %d %H:%M")}] {msg.author.display_name}: {msg.content}')

        transcript = '\n'.join(messages) if messages else 'No messages.'

        # Trouve le membre
        member = None
        if self.member_id:
            member = guild.get_member(self.member_id)
        if not member:
            # Essaie de trouver depuis le topic
            if channel.topic:
                try:
                    member_id = int(channel.topic.split('(')[-1].replace(')', '').strip())
                    member = guild.get_member(member_id)
                except:
                    pass

        # Envoie transcript en DM
        if member:
            try:
                embed_dm = discord.Embed(
                    title='🔒 Your Idea Ticket Has Been Closed',
                    description=(
                        f'Your idea ticket **#{channel.name}** has been closed by the MarketFlow Journal team.\n\n'
                        '📋 **Transcript of your conversation:**'
                    ),
                    color=0x00d4a8
                )
                embed_dm.set_footer(text='MarketFlow Journal — Ticket System')

                # Si transcript trop long, tronque
                transcript_display = transcript[:1800] if len(transcript) > 1800 else transcript
                embed_dm.add_field(
                    name='Messages',
                    value=f'```\n{transcript_display}\n```' if transcript_display else '```\nNo messages\n```',
                    inline=False
                )

                await member.send(embed=embed_dm)
            except:
                pass

        # Log fermeture
        if _log_channel:
            embed_log = discord.Embed(title='🔒 Ticket Closed', color=0xef4444)
            embed_log.add_field(name='Ticket', value=channel.name, inline=False)
            embed_log.add_field(name='Closed by', value=f'{interaction.user.mention}', inline=False)
            if member:
                embed_log.add_field(name='Member', value=f'{member.mention}', inline=False)
            embed_log.set_footer(text='MarketFlow Journal — Ticket System')
            await _log_channel.send(embed=embed_log)

        # Attend 3 secondes puis supprime
        await asyncio.sleep(3)
        await channel.delete()


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(TicketView())
        self.bot.add_view(CloseTicketView())

    @commands.Cog.listener()
    async def on_ready(self):
        global _log_channel
        print('✅ Cog Tickets prêt')

        guild = self.bot.get_guild(int(os.getenv('GUILD_ID')))
        if not guild:
            return

        log_channel_id = int(os.getenv('LOG_CHANNEL_ID', 0))
        _log_channel = guild.get_channel(log_channel_id)

        # Auto-poste le message de tickets dans #support-ticket
        ticket_channel_id = int(os.getenv('TICKET_CHANNEL_ID', 0))
        ticket_channel = guild.get_channel(ticket_channel_id)
        if not ticket_channel:
            print('❌ TICKET_CHANNEL_ID introuvable dans .env')
            return

        messages = [msg async for msg in ticket_channel.history(limit=10)]
        bot_messages = [m for m in messages if m.author == self.bot.user]

        if len(bot_messages) == 1:
            print('✅ Message tickets déjà présent')
            return

        await ticket_channel.purge(limit=100, check=lambda m: m.author == self.bot.user)
        await self._post_ticket_message(ticket_channel)
        print('✅ Message tickets posté')

    async def _post_ticket_message(self, channel):
        embed = discord.Embed(
            title='🎫 MarketFlow Journal — Support Center',
            description=(
                'Welcome to the **MarketFlow Journal** support center.\n\n'
                '**🛠️ Support**\n'
                'Need help with the platform? Click below to access our support team directly on the website.\n\n'
                '**💡 Submit an Idea**\n'
                'Have a feature request or improvement idea? Open a ticket and share it with our team.\n\n'
                '*Our team will review every idea and get back to you.*'
            ),
            color=0x00d4a8
        )
        embed.set_footer(text='MarketFlow Journal — Support Center')
        await channel.send(embed=embed, view=TicketView())

    @app_commands.command(name='setup_tickets', description='Poste le message de tickets')
    async def setup_tickets(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            await interaction.response.send_message('❌ Permission denied.', ephemeral=True)
            return

        await interaction.response.send_message('⏳ Setup en cours...', ephemeral=True)
        await interaction.channel.purge(limit=100, check=lambda m: m.author == self.bot.user)
        await self._post_ticket_message(interaction.channel)


async def setup(bot):
    await bot.add_cog(Tickets(bot))