"""
Discord bot main application.
"""

import os
import asyncio
from datetime import datetime, timedelta
import pytz
import discord
from discord.ext import tasks

from shared.data_manager import DataManager
from shared.constants import InstanceStatus
from discord_bot.services.bot_service import BotService
from discord_bot.services.subscription_service import SubscriptionService
from discord_bot.utils.permissions import init_permission_checker
from discord_bot.commands.user_commands import setup_user_commands
from discord_bot.commands.admin_commands import setup_admin_commands


class WhaleBotDiscord(discord.Bot):
    """Custom Discord bot for WhaleBots management."""
    
    def __init__(self, whalebots_path: str, *args, **kwargs):
        """
        Initialize Discord bot.
        
        Args:
            whalebots_path: Path to WhaleBots installation
        """
        # Setup intents - only enable what we need
        intents = discord.Intents.default()
        intents.guilds = True
        # Don't require privileged intents unless necessary
        # intents.members = True  # Only if you need member info
        # intents.message_content = True  # Only if reading message content
        
        super().__init__(intents=intents, *args, **kwargs)
        
        # Initialize services
        self.data_manager = DataManager()
        self.bot_service = BotService(whalebots_path, self.data_manager)
        self.subscription_service = SubscriptionService(self.data_manager)
        
        # Initialize permission checker
        init_permission_checker(self.data_manager)
        
        # Setup commands
        setup_user_commands(self, self.bot_service, self.subscription_service, self.data_manager)
        setup_admin_commands(self, self.bot_service, self.subscription_service, self.data_manager)
    
    async def on_ready(self):
        """Handle bot ready event."""
        print(f"[OK] Bot logged in as {self.user}")
        print(f"[OK] Connected to {len(self.guilds)} guilds")

        # Sync slash commands
        print("[INFO] Syncing slash commands...")
        await self.sync_commands()
        print("[OK] Slash commands synced")

        # Start background tasks
        if not self.heartbeat_checker.is_running():
            self.heartbeat_checker.start()
            print("[OK] Heartbeat checker started")

        if not self.expiry_checker.is_running():
            self.expiry_checker.start()
            print("[OK] Expiry checker started")

        # Start emulator validator task
        if not self.emulator_validator.is_running():
            self.emulator_validator.start()
            print("[OK] Emulator validator started")

        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="WhaleBots instances"
            )
        )
    
    async def on_application_command_error(self, ctx: discord.ApplicationContext, error: Exception):
        """Handle command errors."""
        print(f"[ERROR] Command error: {error}")
        
        if isinstance(error, discord.errors.ApplicationCommandInvokeError):
            error = error.original
        
        error_message = f"Error: {str(error)}"
        
        try:
            if ctx.response.is_done():
                await ctx.followup.send(error_message, ephemeral=True)
            else:
                await ctx.respond(error_message, ephemeral=True)
        except:
            pass
    
    @tasks.loop(minutes=5)
    async def heartbeat_checker(self):
        """Check for instances with stale heartbeats."""
        try:
            print("[INFO] Checking heartbeats...")
            
            running_users = self.data_manager.get_users_by_status(InstanceStatus.RUNNING)
            now = datetime.now(pytz.UTC)
            timeout_threshold = timedelta(minutes=15)  # 15 minutes timeout
            
            stale_count = 0
            
            for user in running_users:
                if not user.last_heartbeat:
                    continue
                
                try:
                    last_hb = datetime.fromisoformat(user.last_heartbeat)
                    if last_hb.tzinfo is None:
                        last_hb = pytz.UTC.localize(last_hb)
                    
                    time_since_hb = now - last_hb
                    
                    if time_since_hb > timeout_threshold:
                        # Mark as error
                        user.status = InstanceStatus.ERROR.value
                        self.data_manager.save_user(user)
                        stale_count += 1
                        print(f"[WARN] Marked {user.discord_name} as ERROR (stale heartbeat)")
                
                except Exception as e:
                    print(f"Error processing heartbeat for {user.discord_name}: {e}")
            
            if stale_count > 0:
                print(f"[WARN] Found {stale_count} stale instances")
            else:
                print("[OK] All heartbeats OK")
                
        except Exception as e:
            print(f"Error in heartbeat checker: {e}")
    
    @tasks.loop(hours=1)
    async def expiry_checker(self):
        """Check for expired subscriptions."""
        try:
            print("[INFO] Checking expirations...")
            
            expired_users = self.subscription_service.get_expired_users()
            
            for user in expired_users:
                # Stop instance if running
                if user.is_running:
                    print(f"[WARN] Stopping expired instance for {user.discord_name}")
                    self.bot_service.force_stop_instance(user.discord_id)
                
                # Update status
                user.status = InstanceStatus.EXPIRED.value
                self.data_manager.save_user(user)
            
            if expired_users:
                print(f"[WARN] Processed {len(expired_users)} expired subscriptions")
            else:
                print("[OK] No expired subscriptions")
                
        except Exception as e:
            print(f"Error in expiry checker: {e}")
    
    @heartbeat_checker.before_loop
    async def before_heartbeat_checker(self):
        """Wait for bot to be ready before starting heartbeat checker."""
        await self.wait_until_ready()
    
    @expiry_checker.before_loop
    async def before_expiry_checker(self):
        """Wait for bot to be ready before starting expiry checker."""
        await self.wait_until_ready()

    @tasks.loop(minutes=10)
    async def emulator_validator(self):
        """Background emulator validation task."""
        try:
            print("[INFO] Running emulator validation...")

            # Get the WhaleBots instance from bot service
            whalesbot = self.bot_service.get_whalebots_instance()
            if whalesbot:
                # Get emulator validator and run validation
                validator = whalesbot.emulator_validator
                summary = validator.validate_emulator_now()

                print(
                    f"[INFO] Emulator validation completed: "
                    f"{summary.healthy_count} healthy, "
                    f"{summary.unhealthy_count} unhealthy, "
                    f"{summary.missing_count} missing"
                )

                # Log unhealthy emulators for debugging
                for emulator in summary.emulators:
                    if emulator.status != "healthy":
                        print(
                            f"[WARN] Unhealthy emulator '{emulator.name}' "
                            f"(index {emulator.index}): {emulator.issues}"
                        )
            else:
                print("[WARN] No WhaleBots instance available for validation")

        except Exception as e:
            print(f"[ERROR] Error in emulator validator: {e}")

    @emulator_validator.before_loop
    async def before_emulator_validator(self):
        """Wait for bot to be ready before starting emulator validator."""
        await self.wait_until_ready()

    async def close(self):
        """Cleanup on bot shutdown."""
        print("[INFO] Shutting down bot...")

        # Stop background tasks
        if self.heartbeat_checker.is_running():
            self.heartbeat_checker.stop()

        if self.expiry_checker.is_running():
            self.expiry_checker.stop()

        if self.emulator_validator.is_running():
            self.emulator_validator.stop()

        # Cleanup bot service
        self.bot_service.cleanup()

        await super().close()


def create_bot(whalebots_path: str = None) -> WhaleBotDiscord:
    """
    Create and configure Discord bot.
    
    Args:
        whalebots_path: Path to WhaleBots installation (uses env var if None)
        
    Returns:
        Configured WhaleBotDiscord instance
    """
    if whalebots_path is None:
        whalebots_path = os.getenv("WHALEBOTS_PATH", os.getcwd())
    
    return WhaleBotDiscord(whalebots_path=whalebots_path)

