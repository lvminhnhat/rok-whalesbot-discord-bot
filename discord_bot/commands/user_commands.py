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
        result = await bot_service.start_instance(user_id)
        
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
        result = await bot_service.stop_instance(user_id)
        
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
            title="Miner Status",
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
        
        # Add sync notification if state was synchronized
        if status_info.get('state_synced', False):
            embed.add_field(
                name="⚠️ State Synchronization",
                value=status_info.get('sync_message', 'State was synchronized with GUI.'),
                inline=False
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
        name="help",
        description="Bot help and usage guide"
    )
    async def help_command(ctx: discord.ApplicationContext):
        """Show help information."""
        embed = discord.Embed(
            title="Miner Usage Guide",
            description="Game automation bot manager",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Miner Control",
            value=(
                "`/start` - Start your miner\n"
                "`/stop` - Stop your miner\n"
                "`/status` - Check miner status\n"
                "`/expiry` - View subscription info"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Emulator Management",
            value=(
                "`/link <emulator_name>` - Link to an emulator\n"
                "Note: Contact admin to unlink from emulator"
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
            name="Admin Commands",
            value=(
                "Admins have additional commands:\n"
                "• `/grant <user> <days>` - Cấp subscription\n"
                "• `/link_user <user> <emulator>` - Gắn user vào emulator\n"
                "• `/unlink_user <user>` - Unlink user khỏi emulator\n"
                "• `/relink_user <user> <emulator>` - Gắn lại user vào emulator mới\n"
                "• `/unlink_expired` - Unlink tất cả users đã hết hạn\n"
                "• `/delete_expired` - Xóa tất cả users đã hết hạn\n"
                "• `/list_emulators` - View all emulators and their status"
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

    @bot.slash_command(
        name="queue_status",
        description="Check current operation queue status"
    )
    async def queue_status(ctx: discord.ApplicationContext):
        """Check current queue status."""
        # Check if in allowed location
        allowed, error_msg = in_allowed_channel(ctx)
        if not allowed:
            await ctx.respond(error_msg, ephemeral=True)
            return

        user_id = str(ctx.author.id)

        # Get queue info from bot instance
        bot_instance = ctx.bot
        if hasattr(bot_instance, 'operation_queue'):
            queue_info = bot_instance.operation_queue.get_queue_info()
            pending_ops = bot_instance.operation_queue.get_pending_operations(limit=10)

            # Check user's position in queue
            user_pending_ops = [op for op in pending_ops if op['user_name'] == str(ctx.author)]

            embed = discord.Embed(
                title="Queue Status",
                color=discord.Color.blue()
            )

            # Queue statistics
            embed.add_field(
                name="Queue Information",
                value=f"Pending Operations: {queue_info['pending_operations']}\n"
                      f"Currently Processing: {queue_info['processing_operations']}\n"
                      f"Processor Active: {'Yes' if queue_info['is_processing'] else 'No'}",
                inline=True
            )

            # User's queue position
            if user_pending_ops:
                user_op = user_pending_ops[0]
                embed.add_field(
                    name="Your Queue Position",
                    value=f"Operation: {user_op['operation_type'].title()}\n"
                          f"Position: #{user_op['queue_position']}\n"
                          f"Emulator: #{user_op['emulator_index']}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Your Queue Position",
                    value="No pending operations",
                    inline=False
                )

            # Pending operations (show first 5)
            if pending_ops:
                queue_text = ""
                for i, op in enumerate(pending_ops[:5], 1):
                    queue_text += f"#{i}. {op['operation_type'].title()} - {op['user_name']} (Emulator #{op['emulator_index']})\n"

                if len(pending_ops) > 5:
                    queue_text += f"... and {len(pending_ops) - 5} more"

                embed.add_field(
                    name="Pending Operations",
                    value=queue_text,
                    inline=False
                )

            embed.timestamp = datetime.utcnow()
            await ctx.respond(embed=embed, ephemeral=True)
        else:
            await ctx.respond("Queue system is not available.", ephemeral=True)
