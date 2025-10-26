"""
Queued admin commands for Discord bot with queue management support.

This module provides admin commands to monitor and manage the UI operation queue.
"""

import discord
from discord import Option
from datetime import datetime, timedelta
from typing import Optional

from discord_bot.utils.permissions import is_admin, in_allowed_channel
from discord_bot.services.queued_bot_service import QueuedBotService
from discord_bot.services.subscription_service import SubscriptionService
from shared.data_manager import DataManager
from shared.constants import ActionType, ActionResult


def setup_queued_admin_commands(
    bot: discord.Bot,
    bot_service: QueuedBotService,
    subscription_service: SubscriptionService,
    data_manager: DataManager
):
    """
    Setup queued admin commands.

    Args:
        bot: Discord bot instance
        bot_service: Queued bot service instance
        subscription_service: Subscription service instance
        data_manager: Data manager instance
    """

    @bot.slash_command(
        name="queue_info",
        description="View detailed queue information (Admin only)"
    )
    async def queue_info(ctx: discord.ApplicationContext):
        """View detailed queue information."""
        # Check admin permissions
        if not is_admin(ctx):
            await ctx.respond("❌ Admin command only.", ephemeral=True)
            return

        # Check if in allowed location
        allowed, error_msg = in_allowed_channel(ctx)
        if not allowed:
            await ctx.respond(error_msg, ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        # Get detailed queue information
        queue_stats = bot_service.get_queue_info()
        pending_ops = bot_service.get_pending_operations(limit=50)

        # Create main queue info embed
        embed = discord.Embed(
            title="🔧 Queue Management Dashboard",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )

        # Queue Status
        status_color = "🟢" if queue_stats['is_processing'] else "🔴"
        embed.add_field(
            name="📊 Queue Status",
            value=f"{status_color} Processor: {'Active' if queue_stats['is_processing'] else 'Inactive'}\n"
                  f"📋 Pending: {queue_stats['pending_operations']}\n"
                  f"⚡ Processing: {queue_stats['processing_operations']}\n"
                  f"🔢 Max Concurrent: {queue_stats['max_concurrent']}\n"
                  f"📈 Queue Size: {queue_stats['queue_size']}",
            inline=False
        )

        # Statistics
        stats = queue_stats['statistics']
        success_rate = 0
        if stats['total_operations'] > 0:
            success_rate = (stats['completed_operations'] / stats['total_operations']) * 100

        embed.add_field(
            name="📈 Performance Statistics",
            value=f"Total Operations: {stats['total_operations']}\n"
                  f"✅ Completed: {stats['completed_operations']}\n"
                  f"❌ Failed: {stats['failed_operations']}\n"
                  f"⏰ Timeout: {stats['timeout_operations']}\n"
                  f"📊 Success Rate: {success_rate:.1f}%\n"
                  f"⏱️ Avg Wait: {stats['average_wait_time']:.1f}s\n"
                  f"⚡ Avg Execution: {stats['average_execution_time']:.1f}s",
            inline=True
        )

        # System Health
        health_status = "🟢 Healthy"
        if stats['failed_operations'] > stats['completed_operations'] * 0.2:
            health_status = "🟡 Warning"
        if stats['timeout_operations'] > stats['total_operations'] * 0.3:
            health_status = "🔴 Critical"

        embed.add_field(
            name="🏥 System Health",
            value=f"{health_status}\n"
                  f"Error Rate: {(stats['failed_operations'] / max(1, stats['total_operations']) * 100):.1f}%\n"
                  f"Timeout Rate: {(stats['timeout_operations'] / max(1, stats['total_operations']) * 100):.1f}%",
            inline=True
        )

        await ctx.followup.send(embed=embed, ephemeral=True)

        # Send pending operations in separate embed if there are many
        if pending_ops:
            ops_embed = discord.Embed(
                title="📋 Pending Operations",
                color=discord.Color.blue()
            )

            ops_text = ""
            for i, op in enumerate(pending_ops[:20], 1):
                ops_text += f"#{i}. **{op['operation_type'].title()}** - {op['user_name']}\n"
                ops_text += f"   📍 Position: {op['queue_position']}\n"
                ops_text += f"   🎮 Emulator: #{op['emulator_index']}\n"
                ops_text += f"   ⏰ Time: <t:{int(datetime.fromisoformat(op['timestamp']).timestamp())}:R>\n\n"

            if len(pending_ops) > 20:
                ops_text += f"... and {len(pending_ops) - 20} more operations"

            ops_embed.description = ops_text

            await ctx.followup.send(embed=ops_embed, ephemeral=True)

    @bot.slash_command(
        name="cancel_operation",
        description="Cancel a user's pending operation (Admin only)"
    )
    async def cancel_operation(
        ctx: discord.ApplicationContext,
        user: Option(discord.User, "User whose operation to cancel", required=True)
    ):
        """Cancel a pending operation for a user."""
        # Check admin permissions
        if not is_admin(ctx):
            await ctx.respond("❌ Admin command only.", ephemeral=True)
            return

        # Check if in allowed location
        allowed, error_msg = in_allowed_channel(ctx)
        if not allowed:
            await ctx.respond(error_msg, ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        # Cancel user's operation
        result = await bot_service.cancel_user_operation(str(user.id))

        # Log action
        data_manager.log_action(
            user_id=str(ctx.author.id),
            user_name=str(ctx.author),
            action=ActionType.CONFIG_CHANGE,
            details=f"Cancelled operation for {user.name}",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED
        )

        await ctx.followup.send(
            f"{'✅' if result['success'] else '❌'} {result['message']}",
            ephemeral=True
        )

    @bot.slash_command(
        name="force_stop",
        description="Force stop a user's bot with highest priority (Admin only)"
    )
    async def force_stop(
        ctx: discord.ApplicationContext,
        user: Option(discord.User, "User whose bot to force stop", required=True)
    ):
        """Force stop a user's bot with critical priority."""
        # Check admin permissions
        if not is_admin(ctx):
            await ctx.respond("❌ Admin command only.", ephemeral=True)
            return

        # Check if in allowed location
        allowed, error_msg = in_allowed_channel(ctx)
        if not allowed:
            await ctx.respond(error_msg, ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        # Get queue position info before force stop
        queue_info = bot_service.get_queue_info()
        current_position = queue_info.get('pending_operations', 0) + 1

        await ctx.followup.send(
            f"🚨 Force stopping {user.name}'s bot...\n"
            f"Priority: CRITICAL (jumping to front of queue)\n"
            f"Queue position: #{current_position}\n"
            f"⏳ Please wait...",
            ephemeral=True
        )

        # Force stop with critical priority
        result = await bot_service.force_stop_instance(str(user.id))

        # Log action
        data_manager.log_action(
            user_id=str(ctx.author.id),
            user_name=str(ctx.author),
            action=ActionType.CONFIG_CHANGE,
            details=f"Force stopped bot for {user.name}",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED
        )

        await ctx.followup.send(
            f"{'✅' if result['success'] else '❌'} {result['message']}",
            ephemeral=True
        )

    @bot.slash_command(
        name="cleanup_queue",
        description="Clean up old queue operations (Admin only)"
    )
    async def cleanup_queue(
        ctx: discord.ApplicationContext,
        hours: Option(int, "Age of operations to clean up (in hours)", default=24)
    ):
        """Clean up old operations from the queue."""
        # Check admin permissions
        if not is_admin(ctx):
            await ctx.respond("❌ Admin command only.", ephemeral=True)
            return

        # Check if in allowed location
        allowed, error_msg = in_allowed_channel(ctx)
        if not allowed:
            await ctx.respond(error_msg, ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        # Perform cleanup
        try:
            import asyncio
            cleaned_count = bot_service.operation_queue.cleanup_old_operations(hours)

            # Log action
            data_manager.log_action(
                user_id=str(ctx.author.id),
                user_name=str(ctx.author),
                action=ActionType.CONFIG_CHANGE,
                details=f"Cleaned up {cleaned_count} old operations (older than {hours}h)",
                result=ActionResult.SUCCESS
            )

            await ctx.followup.send(
                f"✅ Queue cleanup completed.\n"
                f"Cleaned up {cleaned_count} operations older than {hours} hours.",
                ephemeral=True
            )

        except Exception as e:
            await ctx.followup.send(
                f"❌ Error during cleanup: {str(e)}",
                ephemeral=True
            )

    @bot.slash_command(
        name="restart_queue",
        description="Restart the queue processor (Admin only)"
    )
    async def restart_queue(ctx: discord.ApplicationContext):
        """Restart the queue processor."""
        # Check admin permissions
        if not is_admin(ctx):
            await ctx.respond("❌ Admin command only.", ephemeral=True)
            return

        # Check if in allowed location
        allowed, error_msg = in_allowed_channel(ctx)
        if not allowed:
            await ctx.respond(error_msg, ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        try:
            # Stop current processor
            await bot_service.operation_queue.stop_processor()

            # Wait a moment
            import asyncio
            await asyncio.sleep(1)

            # Start new processor
            await bot_service.operation_queue.start_processor()

            # Log action
            data_manager.log_action(
                user_id=str(ctx.author.id),
                user_name=str(ctx.author),
                action=ActionType.CONFIG_CHANGE,
                details="Restarted queue processor",
                result=ActionResult.SUCCESS
            )

            await ctx.followup.send(
                "✅ Queue processor restarted successfully.",
                ephemeral=True
            )

        except Exception as e:
            await ctx.followup.send(
                f"❌ Error restarting queue processor: {str(e)}",
                ephemeral=True
            )

    @bot.slash_command(
        name="grant",
        description="Grant subscription days to user (Admin only)"
    )
    async def grant(
        ctx: discord.ApplicationContext,
        user: Option(discord.User, "User to grant subscription to", required=True),
        days: Option(int, "Number of days to grant", required=True)
    ):
        """Grant subscription days to a user."""
        # Check admin permissions
        if not is_admin(ctx):
            await ctx.respond("❌ Admin command only.", ephemeral=True)
            return

        # Check if in allowed location
        allowed, error_msg = in_allowed_channel(ctx)
        if not allowed:
            await ctx.respond(error_msg, ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        # Grant subscription
        result = subscription_service.grant_subscription(str(user.id), days)

        # Log action
        data_manager.log_action(
            user_id=str(ctx.author.id),
            user_name=str(ctx.author),
            action=ActionType.CONFIG_CHANGE,
            details=f"Granted {days} days to {user.name}",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED
        )

        await ctx.followup.send(result['message'], ephemeral=True)

    @bot.slash_command(
        name="link_user",
        description="Link user to emulator (Admin only)"
    )
    async def link_user(
        ctx: discord.ApplicationContext,
        user: Option(discord.User, "User to link", required=True),
        emulator: Option(str, "Emulator name", required=True)
    ):
        """Link a user to an emulator."""
        # Check admin permissions
        if not is_admin(ctx):
            await ctx.respond("❌ Admin command only.", ephemeral=True)
            return

        # Check if in allowed location
        allowed, error_msg = in_allowed_channel(ctx)
        if not allowed:
            await ctx.respond(error_msg, ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        # Link user to emulator
        result = bot_service.link_user_to_emulator(
            str(user.id),
            emulator,
            discord_name=str(user)
        )

        # Log action
        data_manager.log_action(
            user_id=str(ctx.author.id),
            user_name=str(ctx.author),
            action=ActionType.CONFIG_CHANGE,
            details=f"Linked {user.name} to {emulator}",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED
        )

        await ctx.followup.send(result['message'], ephemeral=True)

    @bot.slash_command(
        name="unlink_user",
        description="Unlink user from emulator (Admin only)"
    )
    async def unlink_user(
        ctx: discord.ApplicationContext,
        user: Option(discord.User, "User to unlink", required=True)
    ):
        """Unlink a user from their emulator."""
        # Check admin permissions
        if not is_admin(ctx):
            await ctx.respond("❌ Admin command only.", ephemeral=True)
            return

        # Check if in allowed location
        allowed, error_msg = in_allowed_channel(ctx)
        if not allowed:
            await ctx.respond(error_msg, ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        # Check if user has pending operations
        pending_ops = bot_service.get_pending_operations()
        user_pending = [op for op in pending_ops if op['user_name'] == str(user)]

        if user_pending:
            await ctx.followup.send(
                f"❌ Cannot unlink {user.name} - they have pending operations in the queue. "
                f"Use /cancel_operation first.",
                ephemeral=True
            )
            return

        # Unlink user
        result = bot_service.unlink_user_from_emulator(str(user.id))

        # Log action
        data_manager.log_action(
            user_id=str(ctx.author.id),
            user_name=str(ctx.author),
            action=ActionType.CONFIG_CHANGE,
            details=f"Unlinked {user.name} from emulator",
            result=ActionResult.SUCCESS if result['success'] else ActionResult.FAILED
        )

        await ctx.followup.send(result['message'], ephemeral=True)

    @bot.slash_command(
        name="list_emulators",
        description="View all emulators and their status (Admin only)"
    )
    async def list_emulators(ctx: discord.ApplicationContext):
        """View all emulators and their linked users."""
        # Check admin permissions
        if not is_admin(ctx):
            await ctx.respond("❌ Admin command only.", ephemeral=True)
            return

        # Check if in allowed location
        allowed, error_msg = in_allowed_channel(ctx)
        if not allowed:
            await ctx.respond(error_msg, ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        # Get emulator information
        result = bot_service.get_available_emulators()

        if not result['success']:
            await ctx.followup.send(f"❌ Error: {result['message']}", ephemeral=True)
            return

        emulators = result['emulators']

        if not emulators:
            await ctx.followup.send("No emulators found.", ephemeral=True)
            return

        # Create embed
        embed = discord.Embed(
            title="🎮 Emulator Status",
            description=f"Total: {result['count']} emulators",
            color=discord.Color.blue()
        )

        # Group emulators by status
        active_emulators = [emu for emu in emulators if emu['is_active']]
        inactive_emulators = [emu for emu in emulators if not emu['is_active']]
        linked_emulators = [emu for emu in emulators if emu['linked_user']]
        unlinked_emulators = [emu for emu in emulators if not emu['linked_user']]

        embed.add_field(
            name="📊 Summary",
            value=f"🟢 Active: {len(active_emulators)}\n"
                  f"🔴 Inactive: {len(inactive_emulators)}\n"
                  f"🔗 Linked: {len(linked_emulators)}\n"
                  f"⚪ Unlinked: {len(unlinked_emulators)}",
            inline=True
        )

        # List emulators with details
        emu_list = ""
        for emu in emulators:
            status = "🟢" if emu['is_active'] else "🔴"
            linked = f"👤 {emu['linked_user']}" if emu['linked_user'] else "⚪ Unlinked"
            emu_list += f"{status} **#{emu['index']}** - {emu['name']}\n   {linked}\n\n"

        embed.add_field(
            name="📋 Emulator Details",
            value=emu_list,
            inline=False
        )

        embed.timestamp = datetime.utcnow()

        await ctx.followup.send(embed=embed, ephemeral=True)

    @bot.slash_command(
        name="admin_help",
        description="Admin help for queued system (Admin only)"
    )
    async def admin_help(ctx: discord.ApplicationContext):
        """Show admin help for queued system."""
        # Check admin permissions
        if not is_admin(ctx):
            await ctx.respond("❌ Admin command only.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🔧 Admin Commands - Queued System",
            description="Administrative commands for managing the queued bot system",
            color=discord.Color.gold()
        )

        embed.add_field(
            name="📋 Queue Management",
            value=(
                "`/queue_info` - View detailed queue statistics\n"
                "`/cancel_operation <user>` - Cancel user's pending operation\n"
                "`/force_stop <user>` - Force stop with critical priority\n"
                "`/cleanup_queue [hours]` - Clean up old operations\n"
                "`/restart_queue` - Restart queue processor"
            ),
            inline=False
        )

        embed.add_field(
            name="👤 User Management",
            value=(
                "`/grant <user> <days>` - Grant subscription days\n"
                "`/link_user <user> <emulator>` - Link user to emulator\n"
                "`/unlink_user <user>` - Unlink user from emulator\n"
                "`/list_emulators` - View all emulators and status"
            ),
            inline=False
        )

        embed.add_field(
            name="🚨 Priority Levels",
            value=(
                "1. **CRITICAL** - Admin force operations\n"
                "2. **HIGH** - Stop operations\n"
                "3. **NORMAL** - User start operations\n"
                "4. **LOW** - Background tasks"
            ),
            inline=False
        )

        embed.add_field(
            name="⚠️ Important Notes",
            value=(
                "• Queue prevents GUI conflicts\n"
                "• Higher priority operations jump queue\n"
                "• Operations timeout after specified time\n"
                "• Failed operations don't block the queue\n"
                "• System auto-syncs emulator states\n"
                "• All admin actions are logged"
            ),
            inline=False
        )

        embed.add_field(
            name="🔍 Monitoring",
            value=(
                "• Check `/queue_info` regularly\n"
                "• Monitor success/failure rates\n"
                "• Watch timeout rates\n"
                "• Clean up old operations periodically"
            ),
            inline=False
        )

        embed.timestamp = datetime.utcnow()

        await ctx.respond(embed=embed, ephemeral=True)