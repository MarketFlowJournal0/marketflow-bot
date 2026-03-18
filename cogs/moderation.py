import discord
from discord.ext import commands
from discord import app_commands
import os
from datetime import timedelta

def is_owner(user_id: int) -> bool:
    return user_id == int(os.getenv('OWNER_ID', 0))

def is_staff(member: discord.Member) -> bool:
    return is_owner(member.id) or any(r.name == 'MFJ Teams' for r in member.roles)

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print('✅ Cog Moderation prêt')

    async def log_action(self, guild, title, description, color=0x00d4a8):
        log_channel_id = int(os.getenv('LOG_CHANNEL_ID', 0))
        log_channel = guild.get_channel(log_channel_id)
        if log_channel:
            embed = discord.Embed(title=title, description=description, color=color)
            embed.set_footer(text='MarketFlow Journal — Mod Logs')
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        if message.author.guild_permissions.administrator:
            return
        if is_staff(message.author):
            return

        blocked_keywords = ['http://', 'https://', 'discord.gg/']
        for keyword in blocked_keywords:
            if keyword in message.content.lower():
                await message.delete()
                await message.channel.send(
                    f'{message.author.mention} ⚠️ Links are not allowed here.',
                    delete_after=5
                )
                await self.log_action(
                    message.guild,
                    '🔗 Link Blocked',
                    f'**{message.author}** tried to post a link in {message.channel.mention}',
                    color=0xf59e0b
                )
                return

    @app_commands.command(name='kick', description='Kick un membre')
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = 'No reason provided'):
        if not is_staff(interaction.user):
            await interaction.response.send_message('❌ Permission denied.', ephemeral=True)
            return
        await member.kick(reason=reason)
        await interaction.response.send_message(f'✅ **{member}** kicked. Reason: {reason}', ephemeral=True)
        await self.log_action(interaction.guild, '👢 Member Kicked', f'**{member}** kicked by {interaction.user.mention}\nReason: {reason}', color=0xf59e0b)

    @app_commands.command(name='ban', description='Ban un membre')
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = 'No reason provided'):
        if not is_staff(interaction.user):
            await interaction.response.send_message('❌ Permission denied.', ephemeral=True)
            return
        await member.ban(reason=reason)
        await interaction.response.send_message(f'✅ **{member}** banned. Reason: {reason}', ephemeral=True)
        await self.log_action(interaction.guild, '🔨 Member Banned', f'**{member}** banned by {interaction.user.mention}\nReason: {reason}', color=0xef4444)

    @app_commands.command(name='timeout', description='Timeout un membre')
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = 'No reason provided'):
        if not is_staff(interaction.user):
            await interaction.response.send_message('❌ Permission denied.', ephemeral=True)
            return
        await member.timeout(timedelta(minutes=minutes), reason=reason)
        await interaction.response.send_message(f'✅ **{member}** timed out for {minutes} minutes.', ephemeral=True)
        await self.log_action(interaction.guild, '⏱️ Member Timed Out', f'**{member}** timed out for {minutes}min by {interaction.user.mention}\nReason: {reason}', color=0xf59e0b)

    @app_commands.command(name='clear', description='Supprime des messages')
    async def clear(self, interaction: discord.Interaction, amount: int):
        if not is_staff(interaction.user):
            await interaction.response.send_message('❌ Permission denied.', ephemeral=True)
            return
        await interaction.channel.purge(limit=amount)
        await interaction.response.send_message(f'✅ {amount} messages deleted.', ephemeral=True)
        await self.log_action(interaction.guild, '🧹 Messages Cleared', f'{amount} messages deleted in {interaction.channel.mention} by {interaction.user.mention}', color=0x00d4a8)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.log_action(
            member.guild,
            '📥 New Member Joined',
            f'{member.mention} (`{member.id}`) joined the server.',
            color=0x00d4a8
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self.log_action(
            member.guild,
            '📤 Member Left',
            f'**{member}** (`{member.id}`) left the server.',
            color=0xef4444
        )


async def setup(bot):
    await bot.add_cog(Moderation(bot))