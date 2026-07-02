"""
Bot service for managing WhaleBots instances.
"""

import io
import os
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
import pytz
from PIL import Image
import win32gui
import win32ui
import win32con

from whalebots_automation import WhaleBots
from whalebots_automation.exceptions import (
    WhaleBotsError, EmulatorNotFoundError, EmulatorAlreadyRunningError,
    EmulatorNotRunningError, WindowError
)
from shared.models import User, Subscription
from shared.constants import InstanceStatus
from shared.data_manager import DataManager
from .ui_operation_queue import UIOperationQueue, OperationType, Priority, OperationStatus


class BotService:
    """Service for managing bot instances via WhaleBots automation."""
    
    def __init__(self, whalebots_path: str, data_manager: DataManager, operation_queue: Optional[UIOperationQueue] = None):
        """
        Initialize bot service.

        Args:
            whalebots_path: Path to WhaleBots installation
            data_manager: Data manager instance
            operation_queue: Optional UI operation queue instance
        """
        self.whalebots_path = whalebots_path
        self.data_manager = data_manager
        self._whalesbot: Optional[WhaleBots] = None
        self.operation_queue = operation_queue
        self.use_queue = operation_queue is not None
    
    @property
    def whalesbot(self) -> WhaleBots:
        """Get or create WhaleBots instance."""
        if self._whalesbot is None:
            self._whalesbot = WhaleBots(self.whalebots_path)
        return self._whalesbot

    def _get_actual_emulator_state(self, emulator_index: int) -> bool:
        """
        Get the actual running state of an emulator.

        Args:
            emulator_index: Index of the emulator to check

        Returns:
            True if emulator is actually running, False otherwise
        """
        try:
            emulator_states = self.whalesbot.get_emulator_states()
            for state in emulator_states:
                if state.index == emulator_index:
                    # Use the is_active property from EmulatorState class
                    return state.is_active
            return False
        except Exception as e:
            print(f"[ERROR] Failed to get actual emulator state for index {emulator_index}: {e}")
            # Return False on error to be safe - we don't want to start a bot that might already be running
            return False
    
    def _get_live_emulator_index(self, user) -> int:
        """
        Get the live emulator index for a user by resolving their emulator name.
        Updates stored index if stale. Falls back to stored index if resolution fails.
        """
        if not user.emulator_name:
            return user.emulator_index
        try:
            emulator_state = self.whalesbot.get_emulator_state_by_name(user.emulator_name)
            if emulator_state:
                live_index = emulator_state.index
                if live_index != user.emulator_index:
                    # Update stale index in user's emulators list
                    emu_entry = user.get_emulator_by_name(user.emulator_name)
                    if emu_entry:
                        emu_entry['index'] = live_index
                    self.data_manager.save_user(user)
                    print(f"[SYNC] Updated stale index for emulator '{user.emulator_name}' "
                          f"(user {user.discord_name}): now index {live_index}")
                return live_index
        except Exception:
            pass
        return user.emulator_index

    def _is_admin(self, user_id: str) -> bool:
        """Check if a user ID is an admin."""
        config = self.data_manager.get_config()
        return user_id in config.admin_users

    def _resolve_emulator_index(self, user, emulator_name: str, is_admin: bool = False) -> Dict[str, Any]:
        """
        Resolve an emulator name to a live index by querying WhaleBots.
        Always queries by name to handle index reordering.
        Updates stored index if stale.

        Args:
            user: User object (can be None for admins)
            emulator_name: Name of the emulator to resolve
            is_admin: If True, skip ownership check (admins can control any emulator)

        Returns:
            Dict with 'success', 'index', and optionally 'message'
        """
        try:
            # Always query WhaleBots for the live index by name
            emulator_state = self.whalesbot.get_emulator_state_by_name(emulator_name)
            if not emulator_state:
                return {
                    'success': False,
                    'message': f'Emulator "{emulator_name}" not found.'
                }

            live_index = emulator_state.index

            # Check ownership (unless admin)
            if user:
                emu_entry = user.get_emulator_by_name(emulator_name)
                if emu_entry:
                    # Update stored index if it's stale
                    if emu_entry['index'] != live_index:
                        emu_entry['index'] = live_index
                        self.data_manager.save_user(user)
                        print(f"[SYNC] Updated stale index for emulator '{emulator_name}' "
                              f"(user {user.discord_name}): now index {live_index}")
                    return {
                        'success': True,
                        'index': live_index
                    }

                # Not in user's list
                if not is_admin:
                    return {
                        'success': False,
                        'message': f'You are not linked to emulator "{emulator_name}". Use `link {emulator_name}` first.'
                    }

            return {
                'success': True,
                'index': live_index
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error resolving emulator: {str(e)}'
            }

    async def start_instance(self, user_id: str, emulator_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Start bot instance for user.

        Args:
            user_id: Discord user ID
            emulator_name: Optional emulator name to start (uses user's linked emulator if None)

        Returns:
            Result dictionary with success status and message
        """
        is_admin = self._is_admin(user_id)

        user = self.data_manager.get_user(user_id)
        if not user and not is_admin:
            return {
                'success': False,
                'message': "You don't have access. Please contact admin."
            }

        # Resolve emulator — always by name to handle index reordering
        resolve_name = emulator_name
        if not resolve_name:
            if not user or not user.emulator_name:
                return {
                    'success': False,
                    'message': 'You are not linked to any emulator. Use `link <emulator_name>` to link first.'
                }
            resolve_name = user.emulator_name

        resolve_result = self._resolve_emulator_index(user, resolve_name, is_admin=is_admin)
        if not resolve_result['success']:
            return resolve_result
        emulator_index = resolve_result['index']

        # Check subscription (admins bypass)
        if not is_admin and user and user.subscription.is_expired:
            return {
                'success': False,
                'message': f'Your subscription expired on {user.subscription.end_at}. Please renew.'
            }

        # If queue is available, use queued execution
        if self.use_queue and self.operation_queue:
            return await self._queued_start_instance(user, emulator_index, resolve_name)

        emu_label = resolve_name

        try:
            actual_emulator_state = await asyncio.wait_for(
                asyncio.to_thread(self._get_actual_emulator_state, emulator_index),
                timeout=10.0
            )

            if user:
                # DB says RUNNING but the emulator is stopped: sync the status
                # and FALL THROUGH to start it now (previously returned "please
                # try starting again", forcing a second manual command).
                if user.is_running and not actual_emulator_state:
                    print(f"[SYNC] User {user.discord_name} database says RUNNING but emulator is STOPPED. Syncing and starting...")
                    user.status = InstanceStatus.STOPPED.value
                    user.last_stop = datetime.now(pytz.UTC).isoformat()
                    self.data_manager.save_user(user)

                if user.is_running and actual_emulator_state:
                    return {
                        'success': False,
                        'message': 'Your miner is already running.'
                    }

                if not user.is_running and actual_emulator_state:
                    print(f"[SYNC] User {user.discord_name} database says STOPPED but emulator is RUNNING. Syncing state...")
                    user.status = InstanceStatus.RUNNING.value
                    user.last_start = datetime.now(pytz.UTC).isoformat()
                    user.last_heartbeat = datetime.now(pytz.UTC).isoformat()
                    self.data_manager.save_user(user)
                    return {
                        'success': False,
                        'message': 'Detected state inconsistency. Your miner was started outside Discord. Status has been synchronized.'
                    }
            else:
                # Admin with no user record — just check actual state
                if actual_emulator_state:
                    return {
                        'success': False,
                        'message': 'Emulator is already running.'
                    }
        except asyncio.TimeoutError:
            user_label = user.discord_name if user else user_id
            print(f"[ERROR] Timeout checking emulator state for user {user_label}")
            return {
                'success': False,
                'message': 'Timeout checking emulator state. WhaleBots may not be responding. Please try again.'
            }
        except Exception as e:
            user_label = user.discord_name if user else user_id
            print(f"[ERROR] Failed to check emulator state for user {user_label}: {e}")
            return {
                'success': False,
                'message': f'Unable to verify emulator state. Please try again. Error: {str(e)}'
            }

        try:
            await asyncio.wait_for(
                asyncio.to_thread(self.whalesbot.start, emulator_index),
                timeout=120.0   # OCR-anchored locate can take ~1 min for deep rows
            )

            if user:
                user.status = InstanceStatus.RUNNING.value
                user.last_start = datetime.now(pytz.UTC).isoformat()
                user.last_heartbeat = datetime.now(pytz.UTC).isoformat()
                self.data_manager.save_user(user)

            return {
                'success': True,
                'message': f'Bot started for {emu_label}'
            }

        except asyncio.TimeoutError:
            user_label = user.discord_name if user else user_id
            print(f"[ERROR] Timeout starting emulator for user {user_label}")
            if user:
                user.status = InstanceStatus.ERROR.value
                self.data_manager.save_user(user)
            return {
                'success': False,
                'message': 'Timeout starting miner. WhaleBots window may not be responding. Please check manually.'
            }

        except EmulatorAlreadyRunningError:
            if user:
                user.status = InstanceStatus.RUNNING.value
                self.data_manager.save_user(user)
            return {
                'success': False,
                'message': 'Emulator is already running.'
            }

        except (EmulatorNotFoundError, WindowError) as e:
            if user:
                user.status = InstanceStatus.ERROR.value
                self.data_manager.save_user(user)
            return {
                'success': False,
                'message': f'Error starting: {str(e)}'
            }

        except Exception as e:
            if user:
                user.status = InstanceStatus.ERROR.value
                self.data_manager.save_user(user)
            return {
                'success': False,
                'message': f'Unknown error: {str(e)}'
            }
    
    async def stop_instance(self, user_id: str, emulator_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Stop bot instance for user.

        Args:
            user_id: Discord user ID
            emulator_name: Optional emulator name to stop (uses user's linked emulator if None)

        Returns:
            Result dictionary with success status and message
        """
        is_admin = self._is_admin(user_id)

        user = self.data_manager.get_user(user_id)
        if not user and not is_admin:
            return {
                'success': False,
                'message': "You don't have access."
            }

        # Resolve emulator — always by name to handle index reordering
        resolve_name = emulator_name
        if not resolve_name:
            if not user or not user.emulator_name:
                return {
                    'success': False,
                    'message': 'No emulator specified. Use `stop <emulator_name>`.'
                }
            resolve_name = user.emulator_name

        resolve_result = self._resolve_emulator_index(user, resolve_name, is_admin=is_admin)
        if not resolve_result['success']:
            return resolve_result
        emulator_index = resolve_result['index']

        # If queue is available, use queued execution
        if self.use_queue and self.operation_queue:
            return await self._queued_stop_instance(user, emulator_index, resolve_name)

        emu_label = resolve_name

        # Check actual emulator state before proceeding (run in thread to avoid blocking)
        try:
            actual_emulator_state = await asyncio.wait_for(
                asyncio.to_thread(self._get_actual_emulator_state, emulator_index),
                timeout=10.0
            )

            if user:
                # Check if database says running but emulator is actually stopped (GUI stop scenario)
                if user.is_running and not actual_emulator_state:
                    print(f"[SYNC] User {user.discord_name} database says RUNNING but emulator is STOPPED during stop command. Syncing state...")
                    user.status = InstanceStatus.STOPPED.value
                    user.last_stop = datetime.now(pytz.UTC).isoformat()
                    self.data_manager.save_user(user)
                    return {
                        'success': False,
                        'message': 'Your miner is already stopped (state synchronized). No action needed.'
                    }

                # Check if database says stopped but emulator is actually running (GUI start scenario)
                if not user.is_running and actual_emulator_state:
                    print(f"[SYNC] User {user.discord_name} database says STOPPED but emulator is RUNNING during stop command. Syncing state...")
                    user.status = InstanceStatus.RUNNING.value
                    user.last_start = datetime.now(pytz.UTC).isoformat()
                    user.last_heartbeat = datetime.now(pytz.UTC).isoformat()
                    self.data_manager.save_user(user)
                    # Fall through to the stop logic below after sync

                # Check if not running (both database and actual state agree after potential sync)
                if not user.is_running and not actual_emulator_state:
                    return {
                        'success': False,
                        'message': 'Your miner is not running.'
                    }
            else:
                # Admin with no user record — just check actual state
                if not actual_emulator_state:
                    return {
                        'success': False,
                        'message': 'Emulator is not running.'
                    }
        except asyncio.TimeoutError:
            user_label = user.discord_name if user else user_id
            print(f"[ERROR] Timeout checking emulator state for user {user_label}")
            return {
                'success': False,
                'message': 'Timeout checking emulator state. WhaleBots may not be responding. Please try again.'
            }
        except Exception as e:
            user_label = user.discord_name if user else user_id
            print(f"[ERROR] Failed to check emulator state for user {user_label} during stop: {e}")
            return {
                'success': False,
                'message': f'Unable to verify emulator state. Please try again. Error: {str(e)}'
            }

        # Try to stop (run in thread to avoid blocking Discord event loop)
        try:
            await asyncio.wait_for(
                asyncio.to_thread(self.whalesbot.stop, emulator_index),
                timeout=120.0   # OCR-anchored locate can take ~1 min for deep rows
            )

            # Update user status if user record exists
            if user:
                user.status = InstanceStatus.STOPPED.value
                user.last_stop = datetime.now(pytz.UTC).isoformat()
                self.data_manager.save_user(user)

            return {
                'success': True,
                'message': f'Bot stopped for {emu_label}'
            }

        except asyncio.TimeoutError:
            user_label = user.discord_name if user else user_id
            print(f"[ERROR] Timeout stopping emulator for user {user_label}")
            if user:
                user.status = InstanceStatus.ERROR.value
                self.data_manager.save_user(user)
            return {
                'success': False,
                'message': 'Timeout stopping miner. WhaleBots window may not be responding. Please check manually.'
            }

        except EmulatorNotRunningError:
            if user:
                user.status = InstanceStatus.STOPPED.value
                self.data_manager.save_user(user)
            return {
                'success': False,
                'message': 'Emulator is not running.'
            }

        except (EmulatorNotFoundError, WindowError) as e:
            if user:
                user.status = InstanceStatus.ERROR.value
                self.data_manager.save_user(user)
            return {
                'success': False,
                'message': f'Error stopping: {str(e)}'
            }

        except Exception as e:
            if user:
                user.status = InstanceStatus.ERROR.value
                self.data_manager.save_user(user)
            return {
                'success': False,
                'message': f'Unknown error: {str(e)}'
            }
    
    async def _bulk_action(self, user_id: str, action: str) -> Dict[str, Any]:
        """Start or stop ALL emulators a Discord user owns.

        For each emulator we check its ACTUAL live state (per-index, not the
        single user.status field which can't represent multiple emulators):
        already in the desired state -> report it and skip; otherwise run the
        normal queued start/stop for that emulator and report its result.
        """
        assert action in ("start", "stop")
        is_admin = self._is_admin(user_id)
        user = self.data_manager.get_user(user_id)
        if not user or not user.is_linked:
            return {
                'success': False,
                'message': ("You aren't linked to any emulator." if not is_admin
                            else 'No linked emulators for this account; specify a name instead.')
            }

        names = list(user.emulator_names)
        started = action == "start"
        acted, skipped, failed = [], [], []
        for name in names:
            resolve = self._resolve_emulator_index(user, name, is_admin=is_admin)
            if not resolve.get('success'):
                failed.append(f"{name}: {resolve.get('message', 'could not resolve')}")
                continue
            actual_running = self._get_actual_emulator_state(resolve['index'])
            if started and actual_running:
                skipped.append(f"{name}: already running")
                continue
            if not started and not actual_running:
                skipped.append(f"{name}: already stopped")
                continue
            fn = self.start_instance if started else self.stop_instance
            r = await fn(user_id, emulator_name=name)
            if r.get('success'):
                acted.append(f"{name}: {'started' if started else 'stopped'}")
            else:
                failed.append(f"{name}: {r.get('message', 'failed')}")

        verb = "Start" if started else "Stop"
        lines = [f"**{verb} all** — {len(names)} emulator(s):"]
        for grp in (acted, skipped, failed):
            for line in grp:
                lines.append(f"• {line}")
        return {
            'success': not failed and (bool(acted) or bool(skipped)),
            'message': "\n".join(lines),
            'acted': acted, 'skipped': skipped, 'failed': failed,
        }

    async def start_all(self, user_id: str) -> Dict[str, Any]:
        """Start every emulator the user owns (already-running ones reported)."""
        return await self._bulk_action(user_id, "start")

    async def stop_all(self, user_id: str) -> Dict[str, Any]:
        """Stop every emulator the user owns (already-stopped ones reported)."""
        return await self._bulk_action(user_id, "stop")

    def get_status(self, user_id: str) -> Dict[str, Any]:
        """
        Get bot status for user.

        Args:
            user_id: Discord user ID

        Returns:
            Status dictionary
        """
        user = self.data_manager.get_user(user_id)
        if not user:
            return {
                'exists': False,
                'message': "You don't have access."
            }

        # Check actual emulator state and sync if needed
        if user.emulator_index != -1:
            live_index = self._get_live_emulator_index(user)
            actual_emulator_state = self._get_actual_emulator_state(live_index)

            # Auto-sync state if inconsistency detected
            state_synced = False
            sync_message = ""

            if user.is_running and not actual_emulator_state:
                print(f"[SYNC] Status check: User {user.discord_name} database says RUNNING but emulator is STOPPED. Auto-syncing...")
                user.status = InstanceStatus.STOPPED.value
                user.last_stop = datetime.now(pytz.UTC).isoformat()
                self.data_manager.save_user(user)
                state_synced = True
                sync_message = " (State auto-synchronized: was stopped outside Discord)"

            elif not user.is_running and actual_emulator_state:
                print(f"[SYNC] Status check: User {user.discord_name} database says STOPPED but emulator is RUNNING. Auto-syncing...")
                user.status = InstanceStatus.RUNNING.value
                user.last_start = datetime.now(pytz.UTC).isoformat()
                user.last_heartbeat = datetime.now(pytz.UTC).isoformat()
                self.data_manager.save_user(user)
                state_synced = True
                sync_message = " (State auto-synchronized: was started outside Discord)"

        # Build status message - convert to running/stopped text
        status = user.status
        if user.subscription.is_expired:
            status = InstanceStatus.EXPIRED.value

        # Map status to running/stopped text
        if status == InstanceStatus.RUNNING.value:
            status_text = 'Miner is running'
        elif status == InstanceStatus.STOPPED.value:
            status_text = 'Miner is stopped'
        elif status == InstanceStatus.EXPIRED.value:
            status_text = 'Miner is stopped'
        elif status == InstanceStatus.ERROR.value:
            status_text = 'Miner is stopped'
        else:
            status_text = 'Miner is stopped'

        info = {
            'exists': True,
            'status': status_text,
            'symbol': '',
            'emulator_index': user.emulator_index,
            'is_running': user.is_running,
            'uptime_seconds': user.uptime_seconds,
            'last_heartbeat': user.last_heartbeat,
            'subscription_active': user.subscription.is_active,
            'days_left': user.subscription.days_left,
            'state_synced': state_synced if 'state_synced' in locals() else False,
            'sync_message': sync_message if 'sync_message' in locals() else ""
        }

        return info
    
    def update_heartbeat(self, user_id: str) -> None:
        """
        Update heartbeat timestamp for user.
        
        Args:
            user_id: Discord user ID
        """
        user = self.data_manager.get_user(user_id)
        if user and user.is_running:
            user.last_heartbeat = datetime.now(pytz.UTC).isoformat()
            self.data_manager.save_user(user)
    
    async def force_stop_instance(self, user_id: str) -> Dict[str, Any]:
        user = self.data_manager.get_user(user_id)
        if not user:
            return {
                'success': False,
                'message': 'User does not exist.'
            }
        
        try:
            if user.is_running:
                await asyncio.wait_for(
                    asyncio.to_thread(self.whalesbot.stop, user.emulator_index),
                    timeout=120.0   # OCR-anchored locate can take ~1 min for deep rows
                )
            
            user.status = InstanceStatus.STOPPED.value
            user.last_stop = datetime.now(pytz.UTC).isoformat()
            self.data_manager.save_user(user)
            
            return {
                'success': True,
                'message': f'Force stopped bot for {user.discord_name}'
            }
        
        except asyncio.TimeoutError:
            user.status = InstanceStatus.ERROR.value
            self.data_manager.save_user(user)
            return {
                'success': False,
                'message': 'Timeout stopping miner. WhaleBots may not be responding.'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error: {str(e)}'
            }
    
    def get_available_emulators(self) -> Dict[str, Any]:
        """
        Get list of all available emulators.
        
        Returns:
            Dict with emulator list and count
        """
        try:
            emulator_states = self.whalesbot.get_emulator_states()
            emulators = []
            for state in emulator_states:
                emulators.append({
                    'index': state.index,
                    'name': state.emulator_info.name,
                    'is_active': state.is_active,
                    'linked_user': None  # Will be filled later
                })
            
            # Find linked users (multiple users can share an emulator)
            all_users = self.data_manager.get_all_users()
            for emu in emulators:
                linked_users = []
                for user in all_users:
                    if user.emulator_index == emu['index']:
                        linked_users.append(user.discord_name)
                emu['linked_user'] = ", ".join(linked_users) if linked_users else None
            
            return {
                'success': True,
                'emulators': emulators,
                'count': len(emulators)
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error getting emulators: {str(e)}'
            }
    
    def link_user_to_emulator(
        self,
        user_id: str,
        emulator_name: str,
        discord_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Link user to an emulator by name.
        Multiple users can share the same emulator.

        Args:
            user_id: Discord user ID
            emulator_name: Name of the emulator to link
            discord_name: Discord username (used when auto-creating a user record)

        Returns:
            Result dictionary
        """
        user = self.data_manager.get_user(user_id)
        if not user:
            # Auto-create user record with expired subscription placeholder
            now = datetime.now(pytz.UTC)
            subscription = Subscription(
                start_at=now.isoformat(),
                end_at=now.isoformat()
            )
            user = User(
                discord_id=user_id,
                discord_name=discord_name or user_id,
                emulator_index=-1,
                subscription=subscription,
                status=InstanceStatus.STOPPED.value
            )
            self.data_manager.save_user(user)

        # Check if user's bot is running
        if user.is_running:
            return {
                'success': False,
                'message': 'Please stop your miner before changing emulator link.'
            }

        # Find emulator by name
        try:
            emulator_state = self.whalesbot.get_emulator_state_by_name(emulator_name)
            if not emulator_state:
                return {
                    'success': False,
                    'message': f'Emulator "{emulator_name}" not found.'
                }

            # Check if already linked to this emulator
            existing = user.get_emulator_by_name(emulator_state.emulator_info.name)
            if existing:
                return {
                    'success': False,
                    'message': f'Already linked to emulator "{emulator_name}".'
                }

            # Add emulator to user's list (supports multiple emulators)
            user.emulators.append({
                'index': emulator_state.index,
                'name': emulator_state.emulator_info.name
            })
            self.data_manager.save_user(user)

            return {
                'success': True,
                'message': f'Successfully linked to emulator "{emulator_state.emulator_info.name}"!\nYou now have {len(user.emulators)} linked emulator(s).'
            }

        except Exception as e:
            return {
                'success': False,
                'message': f'Error linking emulator: {str(e)}'
            }
    
    def unlink_user_from_emulator(self, user_id: str) -> Dict[str, Any]:
        """
        Unlink user from emulator (set emulator_name to None).
        User account remains but cannot start bot until linked again.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Result dictionary
        """
        user = self.data_manager.get_user(user_id)
        if not user:
            return {
                'success': False,
                'message': "User not found."
            }
        
        # Check if user's bot is running
        if user.is_running:
            return {
                'success': False,
                'message': 'Please stop your miner before unlinking emulator.'
            }
        
        old_emulator = user.emulator_name or f"Index {user.emulator_index}"
        user.emulator_name = None
        user.emulator_index = -1  # -1 means unlinked
        self.data_manager.save_user(user)
        
        return {
            'success': True,
            'message': f'Successfully unlinked from emulator "{old_emulator}".\nYou can link to another emulator using /link command.'
        }
    
    def validate_user_emulators(self) -> Dict[str, Any]:
        """
        Validate all users' emulator links.
        Unlink users if their emulator no longer exists.
        
        Returns:
            Dict with validation results
        """
        try:
            # Get all available emulators
            emulator_states = self.whalesbot.get_emulator_states()
            available_names = {state.emulator_info.name for state in emulator_states}
            available_indices = {state.index for state in emulator_states}
            
            # Check all users
            all_users = self.data_manager.get_all_users()
            unlinked_users = []
            
            for user in all_users:
                # Skip users with no active subscription
                if user.subscription.is_expired:
                    continue
                
                # Check if user's emulator still exists
                needs_unlink = False
                
                if user.emulator_name and user.emulator_name not in available_names:
                    needs_unlink = True
                elif user.emulator_index not in available_indices and user.emulator_index != -1:
                    needs_unlink = True
                
                if needs_unlink:
                    # Force stop if running
                    if user.is_running:
                        try:
                            self.whalesbot.stop(user.emulator_index)
                        except:
                            pass
                        user.status = InstanceStatus.STOPPED.value
                    
                    # Unlink
                    old_name = user.emulator_name or f"Index {user.emulator_index}"
                    user.emulator_name = None
                    user.emulator_index = -1
                    self.data_manager.save_user(user)
                    
                    unlinked_users.append({
                        'user_id': user.discord_id,
                        'user_name': user.discord_name,
                        'old_emulator': old_name
                    })
            
            return {
                'success': True,
                'unlinked_count': len(unlinked_users),
                'unlinked_users': unlinked_users
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error validating emulators: {str(e)}'
            }
    
    def get_whalebots_instance(self):
        """
        Get the WhaleBots instance.

        Returns:
            WhaleBots instance or None if not available
        """
        try:
            return self.whalesbot
        except Exception:
            return None

    @staticmethod
    def _find_emulator_hwnd(emulator_name: str) -> Optional[int]:
        """
        Find the BlueStacks emulator window handle by its display name.

        BlueStacks windows have class 'Qt672QWindowIcon' and their title
        matches the emulator display name configured in WhaleBots.

        Args:
            emulator_name: Display name of the emulator (e.g. 'MinHe')

        Returns:
            Window handle (hwnd) or None if not found
        """
        result = []

        def callback(hwnd, _):
            if win32gui.GetClassName(hwnd) == 'Qt672QWindowIcon':
                if win32gui.GetWindowText(hwnd) == emulator_name:
                    result.append(hwnd)

        win32gui.EnumWindows(callback, None)
        return result[0] if result else None

    @staticmethod
    def _get_game_viewport(hwnd: int):
        """
        Find the game viewport rect within the parent BlueStacks window.

        The BlueStacks parent window contains chrome (top bar, right toolbar).
        The actual game renders in a 'BlueStacksApp' child window. We return
        the child's position relative to the parent's client area so BitBlt
        on the parent can be cropped to just the game content.

        Returns:
            (x, y, w, h) of the game viewport in parent client coords,
            or None to use the full client area as fallback.
        """
        children = []

        def child_cb(child_hwnd, _):
            if win32gui.GetClassName(child_hwnd) == 'BlueStacksApp':
                children.append(child_hwnd)

        win32gui.EnumChildWindows(hwnd, child_cb, None)
        if not children:
            return None

        child_rect = win32gui.GetWindowRect(children[0])
        # Convert child's screen coords to parent's client coords
        x, y = win32gui.ScreenToClient(hwnd, (child_rect[0], child_rect[1]))
        w = child_rect[2] - child_rect[0]
        h = child_rect[3] - child_rect[1]
        return (x, y, w, h)

    def _capture_window(self, hwnd: int) -> Image.Image:
        """
        Capture the game viewport from a BlueStacks window using BitBlt.

        Captures the full parent client area (which includes GPU-rendered game
        content) then crops to just the game viewport, excluding the BlueStacks
        top bar and right toolbar.

        DPI: makes THIS thread per-monitor DPI-aware first so GetClientRect/BitBlt
        use physical pixels (otherwise, on a scaled display e.g. 125%, the capture
        comes out zoomed/cropped). Thread-scoped and restored, so it never changes
        the process-wide DPI mode that the start/stop GUI automation relies on.

        Args:
            hwnd: Window handle to capture

        Returns:
            PIL Image of the game viewport
        """
        from whalebots_automation.services.watchdog_reader import (
            set_thread_dpi_aware, restore_thread_dpi,
        )
        prev_dpi = set_thread_dpi_aware()
        try:
            left, top, right, bottom = win32gui.GetClientRect(hwnd)
            w = right - left
            h = bottom - top

            client_dc = win32gui.GetDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(client_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
            save_dc.SelectObject(bitmap)

            save_dc.BitBlt((0, 0), (w, h), mfc_dc, (0, 0), win32con.SRCCOPY)

            bmp_info = bitmap.GetInfo()
            bmp_bits = bitmap.GetBitmapBits(True)
            img = Image.frombuffer(
                'RGB',
                (bmp_info['bmWidth'], bmp_info['bmHeight']),
                bmp_bits, 'raw', 'BGRX', 0, 1,
            )

            win32gui.DeleteObject(bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, client_dc)

            # Crop to game viewport (exclude BlueStacks chrome)
            viewport = self._get_game_viewport(hwnd)
            if viewport:
                vx, vy, vw, vh = viewport
                img = img.crop((vx, vy, vx + vw, vy + vh))

            return img
        finally:
            restore_thread_dpi(prev_dpi)

    async def screenshot_emulator(self, emulator_name: str) -> Dict[str, Any]:
        """
        Take a screenshot of an emulator window and return the full game viewport.

        Uses Win32 BitBlt to capture the BlueStacks window by its display name,
        which works without bringing the window to the foreground.

        Args:
            emulator_name: Name of the emulator to screenshot

        Returns:
            Dict with 'success', 'image' (BytesIO), and 'name'
        """
        try:
            emulator_state = self.whalesbot.get_emulator_state_by_name(emulator_name)
            if not emulator_state:
                return {'success': False, 'message': f'Emulator "{emulator_name}" not found.'}

            hwnd = await asyncio.to_thread(self._find_emulator_hwnd, emulator_name)
            if not hwnd:
                return {'success': False, 'message': f'Window not found for emulator "{emulator_name}".'}

            img = await asyncio.to_thread(self._capture_window, hwnd)

            buf = io.BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)

            return {'success': True, 'image': buf, 'name': emulator_name}

        except Exception as e:
            return {'success': False, 'message': f'Screenshot error: {str(e)}'}

    def cleanup(self) -> None:
        """Cleanup WhaleBots instance."""
        if self._whalesbot:
            self._whalesbot.cleanup()
            self._whalesbot = None

    async def _queued_start_instance(self, user: User, emulator_index: int, emu_label: str = None) -> Dict[str, Any]:
        """
        Start instance using queue system.

        Args:
            user: User object
            emulator_index: Emulator index to start
            emu_label: Display name for the emulator

        Returns:
            Result dictionary with success status and message
        """
        if emu_label is None:
            emu_label = (user.emulator_name if user else None) or f"#{emulator_index}"
        # Check if user already has pending operations
        pending_ops = self.operation_queue.get_pending_operations()
        user_pending = [op for op in pending_ops if op['user_name'] == user.discord_name]

        if user_pending:
            return {
                'success': False,
                'message': f'You already have a pending operation in the queue (position #{user_pending[0]["queue_position"]}).'
            }

        # Create start operation callback
        async def start_operation():
            # Check actual emulator state before proceeding
            actual_emulator_state = self._get_actual_emulator_state(emulator_index)

            # Check for state inconsistency: database says RUNNING but the
            # emulator is actually stopped. Sync the status and FALL THROUGH to
            # start it in this same operation (previously this returned "please
            # try again", forcing a second manual command for no reason).
            sync_note = ""
            if user.is_running and not actual_emulator_state:
                print(f"[SYNC] User {user.discord_name} database says RUNNING but emulator is STOPPED. Syncing and starting...")
                user.status = InstanceStatus.STOPPED.value
                user.last_stop = datetime.now(pytz.UTC).isoformat()
                self.data_manager.save_user(user)
                sync_note = " (state was out of sync — auto-corrected)"

            # Check if already running
            if user.is_running and actual_emulator_state:
                return {
                    'success': False,
                    'message': 'Your miner is already running.'
                }

            # Check if emulator was started outside Discord
            if not user.is_running and actual_emulator_state:
                print(f"[SYNC] User {user.discord_name} database says STOPPED but emulator is RUNNING. Syncing...")
                user.status = InstanceStatus.RUNNING.value
                user.last_start = datetime.now(pytz.UTC).isoformat()
                user.last_heartbeat = datetime.now(pytz.UTC).isoformat()
                self.data_manager.save_user(user)
                return {
                    'success': False,
                    'message': 'State inconsistency detected. Your miner was started outside Discord. Status synchronized.'
                }

            # Execute start operation. to_thread: the OCR-anchored click takes
            # seconds (longer for accounts deep in the list) and must not block
            # the event loop / Discord heartbeat.
            try:
                await asyncio.to_thread(self.whalesbot.start, emulator_index)

                # Update user status
                user.status = InstanceStatus.RUNNING.value
                user.last_start = datetime.now(pytz.UTC).isoformat()
                user.last_heartbeat = datetime.now(pytz.UTC).isoformat()
                self.data_manager.save_user(user)

                return {
                    'success': True,
                    'message': f'Bot started for {emu_label}{sync_note}'
                }

            except EmulatorAlreadyRunningError:
                # Update status to running anyway
                user.status = InstanceStatus.RUNNING.value
                self.data_manager.save_user(user)
                return {
                    'success': False,
                    'message': 'Emulator is already running.'
                }

            except (EmulatorNotFoundError, WindowError) as e:
                user.status = InstanceStatus.ERROR.value
                self.data_manager.save_user(user)
                return {
                    'success': False,
                    'message': f'Error starting: {str(e)}'
                }

        # Add operation to queue
        operation_id = await self.operation_queue.add_operation(
            operation_type=OperationType.START,
            user_id=user.discord_id,
            user_name=user.discord_name,
            emulator_index=emulator_index,
            priority=Priority.NORMAL,
            timeout=120,   # OCR-anchored locate can take ~1 min for deep list rows
            callback=start_operation,
            metadata={'emulator_name': user.emulator_name}
        )

        # Wait for operation to complete
        result = await self.operation_queue.wait_for_operation(operation_id, timeout=150)

        if result is None:
            return {
                'success': False,
                'message': 'Operation timed out. Please try again or contact admin.'
            }

        if result.status == OperationStatus.COMPLETED:
            return result.result or {'success': False, 'message': 'Unknown error'}
        else:
            return {
                'success': False,
                'message': f'Operation failed: {result.error or "Unknown error"}'
            }

    async def _queued_stop_instance(self, user: User, emulator_index: int, emu_label: str = None) -> Dict[str, Any]:
        """
        Stop instance using queue system.

        Args:
            user: User object
            emulator_index: Emulator index to stop
            emu_label: Display name for the emulator

        Returns:
            Result dictionary with success status and message
        """
        if emu_label is None:
            emu_label = (user.emulator_name if user else None) or f"#{emulator_index}"
        # Check if user already has pending operations
        pending_ops = self.operation_queue.get_pending_operations()
        user_pending = [op for op in pending_ops if op['user_name'] == user.discord_name]

        if user_pending:
            return {
                'success': False,
                'message': f'You already have a pending operation in the queue (position #{user_pending[0]["queue_position"]}).'
            }

        # Create stop operation callback
        async def stop_operation():
            # Check actual emulator state before proceeding
            actual_emulator_state = self._get_actual_emulator_state(emulator_index)

            # Check for state inconsistency
            if user.is_running and not actual_emulator_state:
                print(f"[SYNC] User {user.discord_name} database says RUNNING but emulator is STOPPED during stop. Syncing...")
                user.status = InstanceStatus.STOPPED.value
                user.last_stop = datetime.now(pytz.UTC).isoformat()
                self.data_manager.save_user(user)
                return {
                    'success': False,
                    'message': 'Your miner is already stopped (state synchronized).'
                }

            # Check if database says stopped but emulator is actually running
            if not user.is_running and actual_emulator_state:
                print(f"[SYNC] User {user.discord_name} database says STOPPED but emulator is RUNNING during stop. Syncing...")
                user.status = InstanceStatus.RUNNING.value
                user.last_start = datetime.now(pytz.UTC).isoformat()
                user.last_heartbeat = datetime.now(pytz.UTC).isoformat()
                self.data_manager.save_user(user)

            # Check if not running after potential sync
            if not user.is_running and not actual_emulator_state:
                return {
                    'success': False,
                    'message': 'Your miner is not running.'
                }

            # Execute stop operation (to_thread: see start_operation)
            try:
                await asyncio.to_thread(self.whalesbot.stop, emulator_index)

                # Update user status
                user.status = InstanceStatus.STOPPED.value
                user.last_stop = datetime.now(pytz.UTC).isoformat()
                self.data_manager.save_user(user)

                uptime_text = ""
                if user.uptime_seconds:
                    hours = user.uptime_seconds // 3600
                    minutes = (user.uptime_seconds % 3600) // 60
                    uptime_text = f"\nUptime: {hours}h {minutes}m"

                return {
                    'success': True,
                    'message': f'Bot stopped for {emu_label}'
                }

            except EmulatorNotRunningError:
                # Update status to stopped anyway
                user.status = InstanceStatus.STOPPED.value
                self.data_manager.save_user(user)
                return {
                    'success': False,
                    'message': 'Emulator is not running.'
                }

            except (EmulatorNotFoundError, WindowError) as e:
                user.status = InstanceStatus.ERROR.value
                self.data_manager.save_user(user)
                return {
                    'success': False,
                    'message': f'Error stopping: {str(e)}'
                }

        # Add operation to queue (higher priority for stop)
        operation_id = await self.operation_queue.add_operation(
            operation_type=OperationType.STOP,
            user_id=user.discord_id,
            user_name=user.discord_name,
            emulator_index=emulator_index,
            priority=Priority.HIGH,  # Stop operations have higher priority
            timeout=120,   # OCR-anchored locate can take ~1 min for deep list rows
            callback=stop_operation,
            metadata={'emulator_name': user.emulator_name}
        )

        # Wait for operation to complete
        result = await self.operation_queue.wait_for_operation(operation_id, timeout=150)

        if result is None:
            return {
                'success': False,
                'message': 'Operation timed out. Please try again or contact admin.'
            }

        if result.status == OperationStatus.COMPLETED:
            return result.result or {'success': False, 'message': 'Unknown error'}
        else:
            return {
                'success': False,
                'message': f'Operation failed: {result.error or "Unknown error"}'
            }
