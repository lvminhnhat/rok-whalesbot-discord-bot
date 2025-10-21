"""
User commands for Discord bot.
"""

import discord
from discord import Option
from datetime import datetime

from discord_bot.utils.permissions import in_allowed_channel, check_cooldown
from discord_bot.services.bot_service import BotService
from discord_bot.services.subscription_service import SubscriptionService
from shared.data_manager import DataManager
from shared.constants import ActionType, ActionResult


def setup_user_commands(
    bot: discord.Bot,
    bot_service: BotService,
    subscription_service: SubscriptionService,
    data_manager: DataManager
):
    """
    Setup user commands.
    
    Args:
        bot: Discord bot instance
        bot_service: Bot service instance
        subscription_service: Subscription service instance
        data_manager: Data manager instance
    """
    
    @bot.slash_command(
        name="start",
        description="Start your bot instance"
    )
    async def start(ctx: discord.ApplicationContext):
        """Start user's bot instance."""
        # Check if in allowed location
        allowed, error_msg = in_allowed_channel(ctx)
        if not allowed:
            await ctx.respond(error_msg, ephemeral=True)
            return
        
        user_id = str(ctx.author.id)
        
        # Check cooldown
        can_proceed, cooldown_msg = check_cooldown(user_id)
        if not can_proceed:
            await ctx.respond(cooldown_msg, ephemeral=True)
            data_manager.log_action(
                user_id=user_id,
                user_name=str(ctx.author),
                action=ActionType.START,
                details="Cooldown active",
                result=ActionResult.DENIED
            )
            return
        
        # Defer response as starting might take time
        await ctx.defer(ephemeral=True)
        
        # Start instance
        result = bot_service.start_instance(user_id)
        
        # Log action
        data_manager.log_action(
            user_id=user_id,
            user_name=str(ctx.author),
            action=ActionType.START,
            details=f"Emulator start attempt",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED
        )
        
        await ctx.followup.send(result['message'], ephemeral=True)
    
    @bot.slash_command(
        name="stop",
        description="Stop your bot instance"
    )
    async def stop(ctx: discord.ApplicationContext):
        """Stop user's bot instance."""
        # Check if in allowed location
        allowed, error_msg = in_allowed_channel(ctx)
        if not allowed:
            await ctx.respond(error_msg, ephemeral=True)
            return
        
        user_id = str(ctx.author.id)
        
        # Defer response
        await ctx.defer(ephemeral=True)
        
        # Stop instance
        result = bot_service.stop_instance(user_id)
        
        # Log action
        data_manager.log_action(
            user_id=user_id,
            user_name=str(ctx.author),
            action=ActionType.STOP,
            details=f"Emulator stop attempt",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED
        )
        
        await ctx.followup.send(result['message'], ephemeral=True)
    
    @bot.slash_command(
        name="status",
        description="Check your bot status"
    )
    async def status(ctx: discord.ApplicationContext):
        """Check user's bot status."""
        # Check if in allowed location
        allowed, error_msg = in_allowed_channel(ctx)
        if not allowed:
            await ctx.respond(error_msg, ephemeral=True)
            return

        user_id = str(ctx.author.id)
        
        status_info = bot_service.get_status(user_id)
        
        if not status_info['exists']:
            await ctx.respond(status_info['message'], ephemeral=True)
            return
        
        # Build status embed
        embed = discord.Embed(
            title="Bot Status",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Status",
            value=f"{status_info['symbol']} {status_info['status']}",
            inline=True
        )
        
        embed.add_field(
            name="Emulator",
            value=f"#{status_info['emulator_index']}",
            inline=True
        )
        
        if status_info['is_running'] and status_info['uptime_seconds']:
            hours = status_info['uptime_seconds'] // 3600
            minutes = (status_info['uptime_seconds'] % 3600) // 60
            embed.add_field(
                name="Uptime",
                value=f"{hours}h {minutes}m",
                inline=True
            )
        
        if status_info['last_heartbeat']:
            try:
                hb_dt = datetime.fromisoformat(status_info['last_heartbeat'])
                embed.add_field(
                    name="Last Update",
                    value=f"<t:{int(hb_dt.timestamp())}:R>",
                    inline=True
                )
            except:
                pass
        
        embed.add_field(
            name="Subscription",
            value="Active" if status_info['subscription_active'] else "Expired",
            inline=True
        )
        
        embed.add_field(
            name="Remaining",
            value=f"{status_info['days_left']} days",
            inline=True
        )
        
        embed.timestamp = datetime.utcnow()
        
        await ctx.respond(embed=embed, ephemeral=True)
    
    @bot.slash_command(
        name="expiry",
        description="View your subscription info"
    )
    async def expiry(ctx: discord.ApplicationContext):
        """Check user's subscription expiry."""
        # Check if in allowed location
        allowed, error_msg = in_allowed_channel(ctx)
        if not allowed:
            await ctx.respond(error_msg, ephemeral=True)
            return

        user_id = str(ctx.author.id)
        user = data_manager.get_user(user_id)
        
        if not user:
            await ctx.respond(
                "You don't have access. Please contact admin.",
                ephemeral=True
            )
            return
        
        # Build expiry embed
        embed = discord.Embed(
            title="Subscription Information",
            color=discord.Color.green() if user.subscription.is_active else discord.Color.red()
        )
        
        try:
            start_dt = user.subscription.start_datetime
            end_dt = user.subscription.end_datetime
            
            embed.add_field(
                name="Start",
                value=f"<t:{int(start_dt.timestamp())}:D>",
                inline=True
            )
            
            embed.add_field(
                name="Expires",
                value=f"<t:{int(end_dt.timestamp())}:D>",
                inline=True
            )
            
            embed.add_field(
                name="Remaining",
                value=f"{user.subscription.days_left} days",
                inline=True
            )
            
            if user.subscription.is_active:
                embed.add_field(
                    name="Status",
                    value="Active",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Status",
                    value="Expired - Please renew",
                    inline=False
                )
        except:
            embed.description = "Có lỗi khi hiển thị thông tin subscription."
        
        embed.timestamp = datetime.utcnow()
        embed.set_footer(text=f"User ID: {user_id}")
        
        await ctx.respond(embed=embed, ephemeral=True)
    
    @bot.slash_command(
        name="link",
        description="Link your account to an emulator"
    )
    async def link(
        ctx: discord.ApplicationContext,
        emulator_name: Option(str, "Emulator name to link to", required=True)
    ):
        """Link user to an emulator by name."""
        # Check if in allowed location
        allowed, error_msg = in_allowed_channel(ctx)
        if not allowed:
            await ctx.respond(error_msg, ephemeral=True)
            return
        
        user_id = str(ctx.author.id)
        
        # Defer response
        await ctx.defer(ephemeral=True)
        
        # Link user to emulator
        result = bot_service.link_user_to_emulator(
            user_id,
            emulator_name,
            discord_name=str(ctx.author)
        )
        
        # Log action
        data_manager.log_action(
            user_id=user_id,
            user_name=str(ctx.author),
            action=ActionType.CONFIG_CHANGE,
            details=f"Link to emulator: {emulator_name}",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED
        )
        
        await ctx.followup.send(result['message'], ephemeral=True)
    
    @bot.slash_command(
        name="unlink",
        description="Unlink your account from current emulator"
    )
    async def unlink(ctx: discord.ApplicationContext):
        """Unlink user from emulator."""
        # Check if in allowed location
        allowed, error_msg = in_allowed_channel(ctx)
        if not allowed:
            await ctx.respond(error_msg, ephemeral=True)
            return
        
        user_id = str(ctx.author.id)
        
        # Defer response
        await ctx.defer(ephemeral=True)
        
        # Unlink user
        result = bot_service.unlink_user_from_emulator(user_id)
        
        # Log action
        data_manager.log_action(
            user_id=user_id,
            user_name=str(ctx.author),
            action=ActionType.CONFIG_CHANGE,
            details="Unlink from emulator",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED
        )
        
        await ctx.followup.send(result['message'], ephemeral=True)
    
    @bot.slash_command(
        name="list_emulators",
        description="View all available emulators"
    )
    async def list_emulators(ctx: discord.ApplicationContext):
        """List all available emulators."""
        # Check if in allowed location
        allowed, error_msg = in_allowed_channel(ctx)
        if not allowed:
            await ctx.respond(error_msg, ephemeral=True)
            return
        
        # Defer response
        await ctx.defer(ephemeral=True)
        
        # Get emulators
        result = bot_service.get_available_emulators()
        
        if not result['success']:
            await ctx.followup.send(result['message'], ephemeral=True)
            return
        
        # Build embed
        embed = discord.Embed(
            title="Available Emulators",
            description=f"Total: {result['count']} emulators",
            color=discord.Color.blue()
        )
        
        # Group emulators
        linked = []
        available = []
        
        for emu in result['emulators']:
            status = "[ACTIVE]" if emu['is_active'] else "[INACTIVE]"
            if emu['linked_user']:
                linked.append(f"{status} **{emu['name']}** (Index {emu['index']})\n└─ Linked to: {emu['linked_user']}")
            else:
                available.append(f"{status} **{emu['name']}** (Index {emu['index']})\n└─ Available")
        
        if available:
            embed.add_field(
                name=f"Available ({len(available)})",
                value="\n".join(available[:10]) + ("\n..." if len(available) > 10 else ""),
                inline=False
            )
        
        if linked:
            embed.add_field(
                name=f"Linked ({len(linked)})",
                value="\n".join(linked[:10]) + ("\n..." if len(linked) > 10 else ""),
                inline=False
            )
        
        embed.add_field(
            name="How to Link",
            value="Use `/link <emulator_name>` to link to an emulator\nExample: `/link RoK-01`",
            inline=False
        )
        
        embed.timestamp = datetime.utcnow()
        await ctx.followup.send(embed=embed, ephemeral=True)
    
    @bot.slash_command(
        name="help",
        description="Bot help and usage guide"
    )
    async def help_command(ctx: discord.ApplicationContext):
        """Show help information."""
        embed = discord.Embed(
            title="WhaleBots Usage Guide",
            description="Game automation bot manager",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Bot Control",
            value=(
                "`/start` - Start your bot\n"
                "`/stop` - Stop your bot\n"
                "`/status` - Check bot status\n"
                "`/expiry` - View subscription info"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Emulator Management",
            value=(
                "`/list_emulators` - View all emulators\n"
                "`/link <emulator_name>` - Link to an emulator\n"
                "`/unlink` - Unlink from current emulator"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Help",
            value="`/help` - Show this help message",
            inline=False
        )
        
        embed.add_field(
            name="Important Notes",
            value=(
                "• All commands are private (ephemeral)\n"
                "• Cooldown between start/stop commands\n"
                "• Bot auto-stops when subscription expires\n"
                "• Contact admin for support"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Support",
            value="Contact server admin for support",
            inline=False
        )
        
        embed.timestamp = datetime.utcnow()
        
        await ctx.respond(embed=embed, ephemeral=True)
