"""
Queued user commands for Discord bot with UI operation queue support.

This module provides user commands that work with the queued bot service
to prevent conflicts when multiple users try to control the GUI simultaneously.
"""

import discord
from discord import Option
from datetime import datetime

from discord_bot.utils.permissions import in_allowed_channel
from discord_bot.services.queued_bot_service import QueuedBotService
from discord_bot.services.subscription_service import SubscriptionService
from shared.data_manager import DataManager
from shared.constants import ActionType, ActionResult


def setup_queued_user_commands(
    bot: discord.Bot,
    bot_service: QueuedBotService,
    subscription_service: SubscriptionService,
    data_manager: DataManager
):
    """
    Setup queued user commands.

    Args:
        bot: Discord bot instance
        bot_service: Queued bot service instance
        subscription_service: Subscription service instance
        data_manager: Data manager instance
    """

    @bot.slash_command(
        name="start",
        description="Start your bot instance (queued)"
    )
    async def start(ctx: discord.ApplicationContext):
        """Start user's bot instance with queue support."""
        # Check if in allowed location
        allowed, error_msg = in_allowed_channel(ctx)
        if not allowed:
            await ctx.respond(error_msg, ephemeral=True)
            return

        user_id = str(ctx.author.id)

        # Check for existing pending operations
        pending_ops = bot_service.get_pending_operations()
        user_pending = [op for op in pending_ops if op['user_name'] == str(ctx.author)]

        if user_pending:
            position = user_pending[0]['queue_position']
            await ctx.respond(
                f"⏳ You already have a pending {user_pending[0]['operation_type']} operation "
                f"in the queue at position #{position}. Please wait for it to complete.",
                ephemeral=True
            )
            return

        # Defer response as queue processing might take time
        await ctx.defer(ephemeral=True)

        # Get current queue position
        queue_info = bot_service.get_queue_info()
        current_position = queue_info.get('pending_operations', 0) + 1

        # Send initial message
        await ctx.followup.send(
            f"🔄 Starting your miner...\n"
            f"Queue position: #{current_position}\n"
            f"⏳ Please wait while we process your request.",
            ephemeral=True
        )

        # Start instance through queue
        result = await bot_service.start_instance(user_id)

        # Log action
        data_manager.log_action(
            user_id=user_id,
            user_name=str(ctx.author),
            action=ActionType.START,
            details=f"Queued start attempt",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED
        )

        # Send final result
        await ctx.followup.send(result['message'], ephemeral=True)

    @bot.slash_command(
        name="stop",
        description="Stop your bot instance (queued)"
    )
    async def stop(ctx: discord.ApplicationContext):
        """Stop user's bot instance with queue support."""
        # Check if in allowed location
        allowed, error_msg = in_allowed_channel(ctx)
        if not allowed:
            await ctx.respond(error_msg, ephemeral=True)
            return

        user_id = str(ctx.author.id)

        # Check for existing pending operations
        pending_ops = bot_service.get_pending_operations()
        user_pending = [op for op in pending_ops if op['user_name'] == str(ctx.author)]

        if user_pending:
            position = user_pending[0]['queue_position']
            await ctx.respond(
                f"⏳ You already have a pending {user_pending[0]['operation_type']} operation "
                f"in the queue at position #{position}. Please wait for it to complete.",
                ephemeral=True
            )
            return

        # Defer response
        await ctx.defer(ephemeral=True)

        # Get current queue position
        queue_info = bot_service.get_queue_info()
        current_position = queue_info.get('pending_operations', 0) + 1

        # Send initial message
        await ctx.followup.send(
            f"🔄 Stopping your miner...\n"
            f"Queue position: #{current_position}\n"
            f"⏳ Please wait while we process your request.",
            ephemeral=True
        )

        # Stop instance through queue
        result = await bot_service.stop_instance(user_id)

        # Log action
        data_manager.log_action(
            user_id=user_id,
            user_name=str(ctx.author),
            action=ActionType.STOP,
            details=f"Queued stop attempt",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED
        )

        # Send final result
        await ctx.followup.send(result['message'], ephemeral=True)

    @bot.slash_command(
        name="status",
        description="Check your bot status and queue position"
    )
    async def status(ctx: discord.ApplicationContext):
        """Check user's bot status including queue information."""
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
            title="🤖 Miner Status",
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

        # Add queue information if available
        if status_info.get('queue_info'):
            queue_info = status_info['queue_info']
            embed.add_field(
                name="📋 Queue Status",
                value=f"Operation: {queue_info['operation_type'].title()}\n"
                      f"Position: #{queue_info['queue_position']}\n"
                      f"⏳ Please wait...",
                inline=False
            )

        # Add sync notification if state was synchronized
        if status_info.get('state_synced', False):
            embed.add_field(
                name="⚠️ State Synchronization",
                value=status_info.get('sync_message', 'State was synchronized with GUI.'),
                inline=False
            )

        # Add queue statistics for transparency
        queue_stats = bot_service.get_queue_info()
        if queue_stats.get('pending_operations', 0) > 0:
            embed.add_field(
                name="📊 Queue Information",
                value=f"Pending operations: {queue_stats['pending_operations']}\n"
                      f"Currently processing: {queue_stats['processing_operations']}",
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

        # Check for existing pending operations
        pending_ops = bot_service.get_pending_operations()
        user_pending = [op for op in pending_ops if op['user_name'] == str(ctx.author)]

        if user_pending:
            await ctx.respond(
                f"⏳ You have a pending operation in the queue. "
                f"Please wait for it to complete before linking to a new emulator.",
                ephemeral=True
            )
            return

        # Defer response
        await ctx.defer(ephemeral=True)

        # Link user to emulator (non-blocking operation)
        from discord_bot.services.bot_service import BotService
        legacy_bot_service = BotService(bot_service.whalebots_path, data_manager)
        result = legacy_bot_service.link_user_to_emulator(
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
        name="queue",
        description="Check current queue status"
    )
    async def queue_status(ctx: discord.ApplicationContext):
        """Check current queue status and position."""
        # Check if in allowed location
        allowed, error_msg = in_allowed_channel(ctx)
        if not allowed:
            await ctx.respond(error_msg, ephemeral=True)
            return

        queue_info = bot_service.get_queue_info()
        pending_ops = bot_service.get_pending_operations(limit=10)

        embed = discord.Embed(
            title="📋 Operation Queue Status",
            color=discord.Color.blue()
        )

        # Queue statistics
        embed.add_field(
            name="📊 Queue Statistics",
            value=f"Pending: {queue_info['pending_operations']}\n"
                  f"Processing: {queue_info['processing_operations']}\n"
                  f"Max Concurrent: {queue_info['max_concurrent']}\n"
                  f"Processor Active: {'✅' if queue_info['is_processing'] else '❌'}",
            inline=False
        )

        # Statistics
        stats = queue_info['statistics']
        embed.add_field(
            name="📈 Operation Statistics",
            value=f"Total: {stats['total_operations']}\n"
                  f"Completed: {stats['completed_operations']}\n"
                  f"Failed: {stats['failed_operations']}\n"
                  f"Timeout: {stats['timeout_operations']}\n"
                  f"Avg Wait: {stats['average_wait_time']:.1f}s\n"
                  f"Avg Execution: {stats['average_execution_time']:.1f}s",
            inline=True
        )

        # Current user's position
        user_pending_ops = [op for op in pending_ops if op['user_name'] == str(ctx.author)]
        if user_pending_ops:
            user_op = user_pending_ops[0]
            embed.add_field(
                name="🎯 Your Queue Position",
                value=f"Operation: {user_op['operation_type'].title()}\n"
                      f"Position: #{user_op['queue_position']}\n"
                      f"Emulator: #{user_op['emulator_index']}",
                inline=False
            )

        # Recent operations in queue
        if pending_ops:
            queue_text = ""
            for i, op in enumerate(pending_ops[:5], 1):
                queue_text += f"#{i}. {op['operation_type'].title()} - {op['user_name']} (Emulator #{op['emulator_index']})\n"

            if len(pending_ops) > 5:
                queue_text += f"... and {len(pending_ops) - 5} more"

            embed.add_field(
                name="📝 Pending Operations",
                value=queue_text or "No pending operations",
                inline=False
            )

        embed.timestamp = datetime.utcnow()

        await ctx.respond(embed=embed, ephemeral=True)

    @bot.slash_command(
        name="help",
        description="Bot help and usage guide (queued version)"
    )
    async def help_command(ctx: discord.ApplicationContext):
        """Show help information with queue system details."""
        embed = discord.Embed(
            title="Miner Usage Guide (Queued System)",
            description="Game automation bot manager with operation queue",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="Miner Control",
            value=(
                "`/start` - Start your miner (queued)\n"
                "`/stop` - Stop your miner (queued)\n"
                "`/status` - Check miner status and queue position\n"
                "`/expiry` - View subscription info"
            ),
            inline=False
        )

        embed.add_field(
            name="Queue Management",
            value=(
                "`/queue` - View current queue status\n"
                "All operations are processed sequentially to prevent conflicts"
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
                "• Operations are queued to prevent conflicts\n"
                "• Higher priority for admin/emergency operations\n"
                "• Bot auto-stops when subscription expires\n"
                "• Contact admin for support"
            ),
            inline=False
        )

        embed.add_field(
            name="Queue System Benefits",
            value=(
                "✅ Prevents GUI conflicts\n"
                "✅ Fair processing order\n"
                "✅ Priority for critical operations\n"
                "✅ Status tracking and transparency\n"
                "✅ Error isolation and recovery"
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
                "• `/queue_info` - View detailed queue information\n"
                "• `/cancel_operation <user>` - Cancel user's pending operation"
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