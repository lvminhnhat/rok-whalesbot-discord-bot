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
from discord_bot.services.ui_operation_queue import (
    UIOperationQueue, OperationType, Priority, OperationStatus,
    _seconds_since_last_input,
)
from discord_bot.services.watchdog_service import WatchdogService, WatchEvent
from whalebots_automation.services.watchdog_reader import read_account_log, LogReading
from discord_bot.utils.permissions import (
    init_permission_checker,
    get_instance_channel_ids,
    channel_matches_instance,
    is_admin,
)
from discord_bot.commands.message_commands import setup_message_commands
from discord_bot.commands.admin_commands import setup_admin_commands


# Freeze-watchdog tuning
WATCHDOG_INTERVAL_MIN = 3            # how often to sweep running instances
WATCHDOG_PAUSE_IDLE_SECONDS = 120   # skip a sweep if local input happened within this window


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
        # Privileged intents
        # intents.members = True  # Only if you need member info
        intents.message_content = True  # Required for message-based user commands
        
        super().__init__(intents=intents, *args, **kwargs)
        
        # Initialize services
        self.data_manager = DataManager()

        # Initialize UI operation queue
        self.operation_queue = UIOperationQueue(max_concurrent_operations=1)

        # Initialize bot service with queue support
        self.bot_service = BotService(whalebots_path, self.data_manager, self.operation_queue)
        self.subscription_service = SubscriptionService(self.data_manager)
        
        # Initialize permission checker
        init_permission_checker(self.data_manager)

        # Freeze watchdog (per-account log monitoring)
        self.watchdog_service = WatchdogService()
        self._watchdog_busy = False
        self._watchdog_skip_next = False  # set after a manual /watchdog start
        self.watchdog_enabled = os.getenv("WATCHDOG_ENABLED", "1").strip().lower() not in ("0", "false", "no")
        try:
            self.watchdog_interval_min = max(1, int(os.getenv("WATCHDOG_INTERVAL_MIN", str(WATCHDOG_INTERVAL_MIN))))
        except ValueError:
            self.watchdog_interval_min = WATCHDOG_INTERVAL_MIN
        try:
            self.watchdog_pause_idle = int(os.getenv("WATCHDOG_PAUSE_IDLE_SECONDS", str(WATCHDOG_PAUSE_IDLE_SECONDS)))
        except ValueError:
            self.watchdog_pause_idle = WATCHDOG_PAUSE_IDLE_SECONDS
        self.alert_channel_id = (os.getenv("ALERT_CHANNEL", "") or "").strip() or None
        if not self.alert_channel_id:
            _ids = sorted(get_instance_channel_ids())
            self.alert_channel_id = _ids[0] if _ids else None
        self.alert_mention = (os.getenv("ALERT_MENTION", "") or "").strip()

        # Setup commands
        setup_message_commands(self, self.bot_service, self.subscription_service, self.data_manager)
        setup_admin_commands(self, self.bot_service, self.subscription_service, self.data_manager)
        self._setup_watchdog_command()
    
    def _validate_instance_channels(self, bound_channels):
        """Warn if any INSTANCE_CHANNEL ID can't be resolved to a visible channel.

        Doesn't abort startup — misconfiguration is loud but non-fatal so the
        operator can fix .env and reconnect without needing to kill the process
        via a crash loop.
        """
        unresolved = []
        not_integer = []
        for raw_id in bound_channels:
            try:
                cid = int(raw_id)
            except ValueError:
                not_integer.append(raw_id)
                continue
            if self.get_channel(cid) is None:
                unresolved.append(raw_id)

        if not_integer:
            print(
                f"[ERROR] INSTANCE_CHANNEL contains non-numeric value(s): "
                f"{', '.join(not_integer)} — channel IDs must be numeric."
            )
        if unresolved:
            print(
                f"[ERROR] INSTANCE_CHANNEL id(s) not visible to this bot: "
                f"{', '.join(unresolved)} — check the ID is correct and the bot "
                f"is a member of that channel's guild. This instance will stay "
                f"silent until the ID resolves."
            )
        if not not_integer and not unresolved:
            print(f"[OK] All {len(bound_channels)} INSTANCE_CHANNEL id(s) resolved")

    async def process_application_commands(self, interaction, auto_sync=None):
        """Route slash commands only when the interaction is in this PC's channel.

        With the same bot token running on multiple PCs, every instance receives
        every interaction. Dropping interactions outside INSTANCE_CHANNEL ensures
        exactly one PC responds (the one bound to the command's channel). If
        INSTANCE_CHANNEL is unset, this process handles everything.
        """
        channel_id = str(interaction.channel_id) if interaction.channel_id else None
        if not channel_matches_instance(channel_id):
            return
        await super().process_application_commands(interaction, auto_sync)

    async def on_ready(self):
        """Handle bot ready event."""
        print(f"[OK] Bot logged in as {self.user}")
        print(f"[OK] Connected to {len(self.guilds)} guilds")

        bound_channels = get_instance_channel_ids()
        if bound_channels:
            print(f"[OK] Instance bound to channel(s): {', '.join(sorted(bound_channels))}")
            self._validate_instance_channels(bound_channels)
        else:
            print("[INFO] INSTANCE_CHANNEL not set — handling every channel (single-PC mode)")

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

        # Start state sync task
        if not self.state_sync_task.is_running():
            self.state_sync_task.start()
            print("[OK] State sync task started")

        # Start freeze watchdog
        if not self.freeze_watchdog.is_running():
            try:
                self.freeze_watchdog.change_interval(minutes=self.watchdog_interval_min)
            except Exception:
                pass
            self.freeze_watchdog.start()
            print(f"[OK] Freeze watchdog started (enabled={self.watchdog_enabled}, "
                  f"alert_channel={self.alert_channel_id})")

        # Start UI operation queue processor
        await self.operation_queue.start_processor()
        print("[OK] UI operation queue started")

        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Miner instances"
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
                    if emulator.status.value != "healthy":
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

    @tasks.loop(minutes=3)
    async def state_sync_task(self):
        """Background task to sync states between GUI and Discord."""
        try:
            print("[INFO] Running state synchronization...")

            # Get all users with active subscriptions
            all_users = self.data_manager.get_all_users()
            sync_count = 0

            for user in all_users:
                # Skip users with no emulator or expired subscriptions
                if user.emulator_index == -1 or user.subscription.is_expired:
                    continue

                # Get actual emulator state
                try:
                    live_index = self.bot_service._get_live_emulator_index(user)
                    actual_state = self.bot_service._get_actual_emulator_state(live_index)

                    # Check for inconsistencies
                    if user.is_running and not actual_state:
                        print(f"[SYNC] Background sync: User {user.discord_name} was stopped outside Discord. Updating state...")
                        user.status = InstanceStatus.STOPPED.value
                        user.last_stop = datetime.now(pytz.UTC).isoformat()
                        self.data_manager.save_user(user)
                        sync_count += 1

                    elif not user.is_running and actual_state:
                        print(f"[SYNC] Background sync: User {user.discord_name} was started outside Discord. Updating state...")
                        user.status = InstanceStatus.RUNNING.value
                        user.last_start = datetime.now(pytz.UTC).isoformat()
                        user.last_heartbeat = datetime.now(pytz.UTC).isoformat()
                        self.data_manager.save_user(user)
                        sync_count += 1

                except Exception as e:
                    print(f"[ERROR] Failed to sync state for user {user.discord_name}: {e}")

            if sync_count > 0:
                print(f"[INFO] State synchronization completed: {sync_count} users synced")
            else:
                print("[INFO] State synchronization completed: All states consistent")

        except Exception as e:
            print(f"[ERROR] Error in state sync task: {e}")

    @state_sync_task.before_loop
    async def before_state_sync_task(self):
        """Wait for bot to be ready before starting state sync task."""
        await self.wait_until_ready()

    # ------------------------------------------------------------------
    # Freeze watchdog
    # ------------------------------------------------------------------
    def _running_emulators(self):
        """(running, roster): running = [{index, name}] for emulators currently
        active (state > 0); roster = ALL account names, used to make OCR name
        matching reject look-alike accounts (e.g. KatFruit87 vs KatFruit89)."""
        try:
            res = self.bot_service.get_available_emulators()
            if not res.get("success"):
                return [], []
            emus = res.get("emulators", [])
            running = [{"index": e["index"], "name": e["name"]}
                       for e in emus if e.get("is_active") and e.get("name")]
            roster = [e["name"] for e in emus if e.get("name")]
            return running, roster
        except Exception as e:
            print(f"[WATCHDOG] could not list emulators: {e}")
            return [], []

    async def _queued_read(self, index: int, name: str, roster=None) -> LogReading:
        """Read one account's ACTIVITY LOG through the UI queue at LOW priority,
        so a user's start/stop (NORMAL priority) preempts between reads instead
        of fighting the watchdog for the mouse/window."""
        async def _cb():
            return await asyncio.to_thread(read_account_log, name, None, False, roster)
        try:
            op_id = await self.operation_queue.add_operation(
                operation_type=OperationType.STATUS_CHECK,
                user_id="watchdog",
                user_name="watchdog",
                emulator_index=index,
                priority=Priority.LOW,
                timeout=90,
                callback=_cb,
                metadata={"watchdog": True, "account": name},
            )
            res = await self.operation_queue.wait_for_operation(op_id, timeout=120)
        except Exception as e:
            return LogReading(name, False, error=f"queue error: {e}")
        if res and res.status == OperationStatus.COMPLETED and isinstance(res.result, LogReading):
            return res.result
        err = (res.error if res else "no result") or f"op status {getattr(res, 'status', None)}"
        return LogReading(name, False, error=err)

    async def _send_watchdog_alert(self, ev):
        if not self.alert_channel_id:
            print(f"[WATCHDOG] {ev.kind} {ev.name}: {ev.reason} (no ALERT_CHANNEL configured)")
            return
        channel = self.get_channel(int(self.alert_channel_id))
        if channel is None:
            print(f"[WATCHDOG] alert channel {self.alert_channel_id} not found/visible")
            return
        colors = {"frozen": 0xE74C3C, "still_frozen": 0xE67E22,
                  "recovered": 0x2ECC71, "unreadable": 0x95A5A6}
        titles = {"frozen": "🛑 Instance frozen", "still_frozen": "⏳ Still frozen",
                  "recovered": "✅ Recovered", "unreadable": "⚠️ Log unreadable"}
        embed = discord.Embed(
            title=f"{titles.get(ev.kind, ev.kind)}: {ev.name}",
            description=ev.reason,
            color=colors.get(ev.kind, 0x95A5A6),
        )
        if ev.latest_ts:
            embed.add_field(name="Last log", value=f"`{ev.latest_ts}`", inline=True)
        if ev.recent_lines:
            body = "\n".join(ev.recent_lines[-5:])[:1000]
            embed.add_field(name="Recent log", value=f"```\n{body}\n```", inline=False)
        content = self.alert_mention if (self.alert_mention and ev.kind in ("frozen", "still_frozen", "unreadable")) else None
        try:
            await channel.send(content=content, embed=embed)
        except Exception as e:
            print(f"[WATCHDOG] failed to send alert: {e}")

    async def _watchdog_sweep(self, manual: bool = False):
        """Run one freeze-check sweep (reads serialized via the UI queue at LOW
        priority, so user start/stop commands jump ahead between reads).

        Returns {'swept': n, 'events': [WatchEvent, ...]} or None if skipped
        (another sweep running, or - for scheduled sweeps - disabled/paused).
        `manual` bypasses the enabled and local-input pause checks: an explicit
        /watchdog start is an intentional request, and the UI queue's idle gate
        still keeps the reads from fighting a local user for the mouse.
        """
        if self._watchdog_busy:
            print("[WATCHDOG] previous sweep still running; skipping")
            return None
        if not manual:
            if not self.watchdog_enabled:
                return None
            idle = _seconds_since_last_input()
            if self.watchdog_pause_idle > 0 and idle is not None and idle < self.watchdog_pause_idle:
                print(f"[WATCHDOG] paused — local input {idle:.0f}s ago")
                return None
        emus, roster = self._running_emulators()
        if not emus:
            return {"swept": 0, "events": []}
        self._watchdog_busy = True
        events = []
        try:
            print(f"[WATCHDOG] sweeping {len(emus)} instance(s)"
                  f"{' (manual)' if manual else ''}...")
            for emu in emus:
                if not manual and not self.watchdog_enabled:
                    break  # toggled off mid-sweep
                reading = await self._queued_read(emu["index"], emu["name"], roster)
                print(f"[WATCHDOG]   {emu['name']} (idx {emu['index']}): "
                      f"ok={reading.ok} ts={reading.latest_ts} err={reading.error}")
                ev = self.watchdog_service.process_reading(emu["name"], reading)
                if ev:
                    print(f"[WATCHDOG] {ev.kind}: {ev.name} — {ev.reason}")
                    events.append(ev)
                    await self._send_watchdog_alert(ev)
        except Exception as e:
            print(f"[ERROR] watchdog sweep: {e}")
        finally:
            self._watchdog_busy = False
        return {"swept": len(emus), "events": events}

    @tasks.loop(minutes=WATCHDOG_INTERVAL_MIN)
    async def freeze_watchdog(self):
        if self._watchdog_skip_next:
            # A manual /watchdog start just finished and restarted this loop;
            # consume the immediate post-restart tick so the next automatic
            # sweep lands a full interval after the manual one.
            self._watchdog_skip_next = False
            return
        await self._watchdog_sweep(manual=False)

    @freeze_watchdog.before_loop
    async def before_freeze_watchdog(self):
        await self.wait_until_ready()

    def _setup_watchdog_command(self):
        bot = self

        @bot.slash_command(name="watchdog",
                           description="Freeze watchdog: on/off, status, or run a check now")
        async def watchdog(ctx: discord.ApplicationContext,
                           action: discord.Option(str, "on / off / status / start / test",
                                                   choices=["on", "off", "status", "start", "test"]) = "status"):
            if not is_admin(ctx):
                await ctx.respond("You don't have permission to use this.", ephemeral=True)
                return
            if action == "on":
                bot.watchdog_enabled = True
                await ctx.respond("✅ Freeze watchdog **enabled**.", ephemeral=True)
            elif action == "off":
                bot.watchdog_enabled = False
                await ctx.respond("⏸️ Freeze watchdog **disabled** — it won't touch the mouse.",
                                  ephemeral=True)
            elif action == "start":
                if bot._watchdog_busy:
                    await ctx.respond("⏳ A sweep is already running — results will post as usual.",
                                      ephemeral=True)
                    return
                await ctx.respond(
                    f"🔍 Freeze check started. The next automatic check moves to "
                    f"~{bot.watchdog_interval_min} min after this one finishes.",
                    ephemeral=True)

                async def _manual_sweep():
                    summary = await bot._watchdog_sweep(manual=True)
                    # Reschedule the loop so the next auto sweep is a full
                    # interval away (the immediate post-restart tick is skipped).
                    if bot.freeze_watchdog.is_running():
                        bot._watchdog_skip_next = True
                        bot.freeze_watchdog.restart()
                    if summary is None:
                        msg = "⚠️ Sweep skipped — another sweep was already running."
                    elif summary["swept"] == 0:
                        msg = "ℹ️ Freeze check done — no running instances to check."
                    else:
                        flagged = [f"**{e.name}** ({e.kind})" for e in summary["events"]]
                        msg = (f"✅ Freeze check done — {summary['swept']} instance(s) checked; "
                               + (f"flagged: {', '.join(flagged)}" if flagged else "nothing flagged."))
                    try:
                        await ctx.followup.send(msg, ephemeral=True)
                    except Exception as e:
                        print(f"[WATCHDOG] manual sweep summary not delivered: {e} — {msg}")

                asyncio.create_task(_manual_sweep())
            elif action == "test":
                await bot._send_watchdog_alert(WatchEvent(
                    name="TEST", kind="frozen",
                    reason="manual test of the alert pipeline (/watchdog test)",
                    latest_ts="00:00:00",
                    recent_lines=["[00:00:00] this is a test alert"]))
                await ctx.respond(
                    f"Sent a test alert to channel `{bot.alert_channel_id}` "
                    f"(mention: `{bot.alert_mention or 'none'}`).", ephemeral=True)
            else:
                state = "enabled" if bot.watchdog_enabled else "disabled"
                tracked = len(bot.watchdog_service.states)
                frozen = sum(1 for s in bot.watchdog_service.states.values() if s.frozen)
                await ctx.respond(
                    f"Freeze watchdog is **{state}**. Tracking {tracked} instance(s); "
                    f"{frozen} currently flagged frozen.",
                    ephemeral=True,
                )

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

        if self.state_sync_task.is_running():
            self.state_sync_task.stop()

        if self.freeze_watchdog.is_running():
            self.freeze_watchdog.stop()

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

