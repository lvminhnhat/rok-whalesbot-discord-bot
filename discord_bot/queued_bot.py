"""
Queued Discord Bot for WhaleBots with UI operation queue support.

This bot extends the base functionality to include queued UI operations
to prevent conflicts when multiple users try to control the GUI simultaneously.
"""

import asyncio
import discord
from datetime import datetime, timedelta
import pytz
import logging

from discord_bot.utils.permissions import init_permission_checker
from discord_bot.services.queued_bot_service import QueuedBotService
from discord_bot.services.subscription_service import SubscriptionService
from discord_bot.commands.queued_user_commands import setup_queued_user_commands
from discord_bot.commands.queued_admin_commands import setup_queued_admin_commands
from shared.data_manager import DataManager


class QueuedWhaleBotsBot(discord.Bot):
    """
    Discord bot with queued UI operations for WhaleBots management.
    """

    def __init__(self, data_manager: DataManager, whalebots_path: str):
        """
        Initialize the queued bot.

        Args:
            data_manager: Data manager instance
            whalebots_path: Path to WhaleBots installation
        """
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            intents=intents,
            command_prefix="!",
            help_command=None
        )

        self.data_manager = data_manager
        self.whalebots_path = whalebots_path

        # Initialize services
        self.subscription_service = SubscriptionService(data_manager)
        self.bot_service = QueuedBotService(whalebots_path, data_manager)

        # Setup commands
        setup_queued_user_commands(self, self.bot_service, self.subscription_service, data_manager)
        setup_queued_admin_commands(self, self.bot_service, self.subscription_service, data_manager)

        # Initialize permission checker
        init_permission_checker(data_manager)

        # Setup logging
        self.logger = logging.getLogger("QueuedWhaleBotsBot")
        self.setup_logging()

        # Task tracking
        self._tasks = []

    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    async def on_ready(self):
        """Called when the bot is ready."""
        self.logger.info(f"Logged in as {self.user}")
        self.logger.info(f"Bot ID: {self.user.id}")
        self.logger.info("Queued WhaleBots Bot is ready!")

        # Sync commands
        await self.sync_commands()
        self.logger.info("Commands synchronized")

        # Start background tasks
        await self.start_background_tasks()

        # Start queue processor
        await self.bot_service.ensure_processor_started()
        self.logger.info("Queue processor started")

        # Set presence
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Queued Miner Operations"
            )
        )

        self.logger.info("Background tasks started")

    async def on_application_command_error(self, ctx: discord.ApplicationContext, error: Exception):
        """Handle application command errors."""
        self.logger.error(f"Command error: {error}")

        if isinstance(error, discord.ApplicationCommandInvokeError):
            error = error.original

        error_message = "❌ An error occurred while processing your command."

        if isinstance(error, discord.CheckFailure):
            error_message = "❌ You don't have permission to use this command."
        elif isinstance(error, discord.ApplicationError):
            error_message = f"❌ {str(error)}"

        try:
            if ctx.response.is_done():
                await ctx.followup.send(error_message, ephemeral=True)
            else:
                await ctx.respond(error_message, ephemeral=True)
        except:
            self.logger.error("Failed to send error message to user")

    async def start_background_tasks(self):
        """Start background tasks."""
        # Heartbeat checker
        self._tasks.append(asyncio.create_task(self.heartbeat_checker()))

        # Expiry checker
        self._tasks.append(asyncio.create_task(self.expiry_checker()))

        # Queue statistics reporter
        self._tasks.append(asyncio.create_task(self.queue_stats_reporter()))

        # Old operations cleanup
        self._tasks.append(asyncio.create_task(self.cleanup_task()))

    async def before_heartbeat_checker(self):
        """Wait until bot is ready before starting heartbeat checker."""
        await self.wait_until_ready()

    async def heartbeat_checker(self):
        """Check heartbeat of running instances."""
        await self.before_heartbeat_checker()
        self.logger.info("Heartbeat checker started")

        while not self.is_closed():
            try:
                # Get all users
                all_users = self.data_manager.get_all_users()

                for user in all_users:
                    if user.is_running:
                        # Update heartbeat if needed
                        self.bot_service.update_heartbeat(user.discord_id)

                await asyncio.sleep(300)  # Check every 5 minutes

            except Exception as e:
                self.logger.error(f"Heartbeat checker error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error

    async def before_expiry_checker(self):
        """Wait until bot is ready before starting expiry checker."""
        await self.wait_until_ready()

    async def expiry_checker(self):
        """Check and handle expired subscriptions."""
        await self.before_expiry_checker()
        self.logger.info("Expiry checker started")

        while not self.is_closed():
            try:
                # Get all users
                all_users = self.data_manager.get_all_users()

                for user in all_users:
                    if user.subscription.is_expired and user.is_running:
                        self.logger.info(f"Stopping expired user: {user.discord_name}")

                        # Force stop expired user's bot
                        result = await self.bot_service.force_stop_instance(user.discord_id)

                        # Log action
                        self.data_manager.log_action(
                            user_id="SYSTEM",
                            user_name="Auto-Expiry",
                            action="AUTO_STOP",
                            details=f"Stopped expired user {user.discord_name}",
                            result="SUCCESS" if result['success'] else "FAILED"
                        )

                await asyncio.sleep(3600)  # Check every hour

            except Exception as e:
                self.logger.error(f"Expiry checker error: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

    async def before_queue_stats_reporter(self):
        """Wait until bot is ready before starting queue stats reporter."""
        await self.wait_until_ready()

    async def queue_stats_reporter(self):
        """Report queue statistics periodically."""
        await self.before_queue_stats_reporter()
        self.logger.info("Queue statistics reporter started")

        while not self.is_closed():
            try:
                # Get queue statistics
                queue_info = self.bot_service.get_queue_info()
                stats = queue_info['statistics']

                # Log statistics
                self.logger.info(
                    f"Queue Stats - Pending: {queue_info['pending_operations']}, "
                    f"Processing: {queue_info['processing_operations']}, "
                    f"Total: {stats['total_operations']}, "
                    f"Success Rate: {(stats['completed_operations'] / max(1, stats['total_operations']) * 100):.1f}%"
                )

                # Check for issues
                if stats['timeout_operations'] > stats['completed_operations'] * 0.2:
                    self.logger.warning("High timeout rate detected!")

                if stats['failed_operations'] > stats['completed_operations'] * 0.1:
                    self.logger.warning("High failure rate detected!")

                await asyncio.sleep(1800)  # Report every 30 minutes

            except Exception as e:
                self.logger.error(f"Queue stats reporter error: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

    async def before_cleanup_task(self):
        """Wait until bot is ready before starting cleanup task."""
        await self.wait_until_ready()

    async def cleanup_task(self):
        """Periodic cleanup of old operations."""
        await self.before_cleanup_task()
        self.logger.info("Cleanup task started")

        while not self.is_closed():
            try:
                # Clean up old operations (older than 12 hours)
                cleaned_count = self.bot_service.operation_queue.cleanup_old_operations(hours=12)

                if cleaned_count > 0:
                    self.logger.info(f"Cleaned up {cleaned_count} old operations")

                await asyncio.sleep(21600)  # Clean up every 6 hours

            except Exception as e:
                self.logger.error(f"Cleanup task error: {e}")
                await asyncio.sleep(1800)  # Wait 30 minutes on error

    async def close(self):
        """Clean shutdown of the bot."""
        self.logger.info("Shutting down bot...")

        # Cancel all background tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Cleanup bot service
        await self.bot_service.cleanup()

        await super().close()
        self.logger.info("Bot shutdown complete")


def create_queued_bot(data_manager: DataManager, whalebots_path: str) -> QueuedWhaleBotsBot:
    """
    Create and configure the queued bot instance.

    Args:
        data_manager: Data manager instance
        whalebots_path: Path to WhaleBots installation

    Returns:
        Configured bot instance
    """
    bot = QueuedWhaleBotsBot(data_manager, whalebots_path)
    return bot


async def run_queued_bot(data_manager: DataManager, whalebots_path: str, token: str):
    """
    Run the queued bot.

    Args:
        data_manager: Data manager instance
        whalebots_path: Path to WhaleBots installation
        token: Discord bot token
    """
    bot = create_queued_bot(data_manager, whalebots_path)

    try:
        await bot.start(token)
    except KeyboardInterrupt:
        await bot.close()
    except Exception as e:
        logging.error(f"Bot error: {e}")
        await bot.close()
        raise


if __name__ == "__main__":
    import sys
    import os
    from pathlib import Path

    # Add project root to Python path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    from shared.data_manager import DataManager
    from shared.constants import DATA_DIR

    # Load configuration
    data_manager = DataManager(DATA_DIR)
    config = data_manager.get_config()

    # Get bot token
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: DISCORD_BOT_TOKEN environment variable not set")
        sys.exit(1)

    # Get WhaleBots path
    whalebots_path = os.getenv("WHALEBOTS_PATH", ".")
    if not os.path.exists(whalebots_path):
        print(f"Error: WhaleBots path not found: {whalebots_path}")
        sys.exit(1)

    # Run bot
    asyncio.run(run_queued_bot(data_manager, whalebots_path, token))