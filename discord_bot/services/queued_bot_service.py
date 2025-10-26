"""
Queued Bot Service for WhaleBots with UI operation queue support.

This service extends the base BotService to include queue-based UI operations
to prevent conflicts when multiple users try to control the GUI simultaneously.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
import pytz

from whalebots_automation import WhaleBots
from whalebots_automation.exceptions import (
    WhaleBotsError, EmulatorNotFoundError, EmulatorAlreadyRunningError,
    EmulatorNotRunningError, WindowError
)
from shared.models import User, Subscription
from shared.constants import InstanceStatus
from shared.data_manager import DataManager

from .ui_operation_queue import (
    UIOperationQueue, OperationType, Priority, OperationStatus
)


class QueuedBotService:
    """
    Bot service with queued UI operations for managing WhaleBots instances.
    """

    def __init__(self, whalebots_path: str, data_manager: DataManager):
        """
        Initialize queued bot service.

        Args:
            whalebots_path: Path to WhaleBots installation
            data_manager: Data manager instance
        """
        self.whalebots_path = whalebots_path
        self.data_manager = data_manager
        self._whalesbot: Optional[WhaleBots] = None

        # Initialize UI operation queue
        self.operation_queue = UIOperationQueue(max_concurrent_operations=1)

        # UI lock for preventing concurrent GUI operations
        self._ui_lock = asyncio.Lock()

        # Track processor task
        self._processor_started = False

    @property
    def whalesbot(self) -> WhaleBots:
        """Get or create WhaleBots instance."""
        if self._whalesbot is None:
            self._whalesbot = WhaleBots(self.whalebots_path)
        return self._whalesbot

    async def ensure_processor_started(self) -> None:
        """Ensure the queue processor is started."""
        if not self._processor_started:
            await self.operation_queue.start_processor()
            self._processor_started = True

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
                    # Handle different possible state properties
                    if hasattr(state, 'is_running'):
                        return state.is_running
                    elif hasattr(state, 'running'):
                        return state.running
                    elif hasattr(state, 'status') and state.status == 'running':
                        return True
            return False
        except Exception as e:
            print(f"[ERROR] Failed to get actual emulator state for index {emulator_index}: {e}")
            return False

    async def start_instance(self, user_id: str) -> Dict[str, Any]:
        """
        Queue bot instance start operation for user.

        Args:
            user_id: Discord user ID

        Returns:
            Result dictionary with success status and message
        """
        await self.ensure_processor_started()

        user = self.data_manager.get_user(user_id)
        if not user:
            return {
                'success': False,
                'message': "You don't have access. Please contact admin."
            }

        # Check if user is linked to an emulator
        if user.emulator_index == -1:
            return {
                'success': False,
                'message': 'You are not linked to any emulator. Please use /link <emulator_name> to link first.'
            }

        # Check subscription
        if user.subscription.is_expired:
            return {
                'success': False,
                'message': f'Your subscription expired on {user.subscription.end_at}. Please renew.'
            }

        # Check if user already has a pending operation
        pending_ops = self.operation_queue.get_pending_operations()
        user_pending = [op for op in pending_ops if op['user_name'] == user.discord_name]
        if user_pending:
            return {
                'success': False,
                'message': f'You already have a pending operation in the queue (position #{user_pending[0]["queue_position"]}).'
            }

        # Create start operation callback
        async def start_operation():
            async with self._ui_lock:
                # Check actual emulator state before proceeding
                actual_emulator_state = self._get_actual_emulator_state(user.emulator_index)

                # Check for state inconsistency
                if user.is_running and not actual_emulator_state:
                    print(f"[SYNC] User {user.discord_name} database says RUNNING but emulator is STOPPED. Syncing...")
                    user.status = InstanceStatus.STOPPED.value
                    user.last_stop = datetime.now(pytz.UTC).isoformat()
                    self.data_manager.save_user(user)
                    return {
                        'success': False,
                        'message': 'State inconsistency detected. Status synchronized. Please try again.'
                    }

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

                # Execute start operation
                try:
                    self.whalesbot.start(user.emulator_index)

                    # Update user status
                    user.status = InstanceStatus.RUNNING.value
                    user.last_start = datetime.now(pytz.UTC).isoformat()
                    user.last_heartbeat = datetime.now(pytz.UTC).isoformat()
                    self.data_manager.save_user(user)

                    return {
                        'success': True,
                        'message': f'Miner started successfully!\nEmulator: {user.emulator_index}\nTime left: {user.subscription.days_left} days'
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
            user_id=user_id,
            user_name=user.discord_name,
            emulator_index=user.emulator_index,
            priority=Priority.NORMAL,
            timeout=60,
            callback=start_operation,
            metadata={'emulator_name': user.emulator_name}
        )

        # Wait for operation to complete
        result = await self.operation_queue.wait_for_operation(operation_id, timeout=120)

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

    async def stop_instance(self, user_id: str) -> Dict[str, Any]:
        """
        Queue bot instance stop operation for user.

        Args:
            user_id: Discord user ID

        Returns:
            Result dictionary with success status and message
        """
        await self.ensure_processor_started()

        user = self.data_manager.get_user(user_id)
        if not user:
            return {
                'success': False,
                'message': "You don't have access."
            }

        # Check if user already has a pending operation
        pending_ops = self.operation_queue.get_pending_operations()
        user_pending = [op for op in pending_ops if op['user_name'] == user.discord_name]
        if user_pending:
            return {
                'success': False,
                'message': f'You already have a pending operation in the queue (position #{user_pending[0]["queue_position"]}).'
            }

        # Create stop operation callback
        async def stop_operation():
            async with self._ui_lock:
                # Check actual emulator state before proceeding
                actual_emulator_state = self._get_actual_emulator_state(user.emulator_index)

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

                # Execute stop operation
                try:
                    self.whalesbot.stop(user.emulator_index)

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
                        'message': f'Miner stopped successfully!{uptime_text}'
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
            user_id=user_id,
            user_name=user.discord_name,
            emulator_index=user.emulator_index,
            priority=Priority.HIGH,  # Stop operations have higher priority
            timeout=45,
            callback=stop_operation,
            metadata={'emulator_name': user.emulator_name}
        )

        # Wait for operation to complete
        result = await self.operation_queue.wait_for_operation(operation_id, timeout=90)

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

    def get_status(self, user_id: str) -> Dict[str, Any]:
        """
        Get bot status for user (non-blocking, no queue needed).

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

        # Check if user has operations in queue
        pending_ops = self.operation_queue.get_pending_operations()
        user_pending_ops = [op for op in pending_ops if op['user_name'] == user.discord_name]

        queue_info = None
        if user_pending_ops:
            queue_info = {
                'has_pending_operation': True,
                'queue_position': user_pending_ops[0]['queue_position'],
                'operation_type': user_pending_ops[0]['operation_type']
            }

        # Check actual emulator state and sync if needed
        if user.emulator_index != -1:
            actual_emulator_state = self._get_actual_emulator_state(user.emulator_index)

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

        # Build status message
        status_symbols = {
            InstanceStatus.RUNNING.value: '[RUNNING]',
            InstanceStatus.STOPPED.value: '[STOPPED]',
            InstanceStatus.EXPIRED.value: '[EXPIRED]',
            InstanceStatus.ERROR.value: '[ERROR]'
        }

        status = user.status
        if user.subscription.is_expired:
            status = InstanceStatus.EXPIRED.value

        symbol = status_symbols.get(status, '[UNKNOWN]')

        info = {
            'exists': True,
            'status': status,
            'symbol': symbol,
            'emulator_index': user.emulator_index,
            'is_running': user.is_running,
            'uptime_seconds': user.uptime_seconds,
            'last_heartbeat': user.last_heartbeat,
            'subscription_active': user.subscription.is_active,
            'days_left': user.subscription.days_left,
            'state_synced': state_synced if 'state_synced' in locals() else False,
            'sync_message': sync_message if 'sync_message' in locals() else "",
            'queue_info': queue_info
        }

        return info

    async def force_stop_instance(self, user_id: str) -> Dict[str, Any]:
        """
        Force stop instance (for admin use) with highest priority.

        Args:
            user_id: Discord user ID

        Returns:
            Result dictionary
        """
        await self.ensure_processor_started()

        user = self.data_manager.get_user(user_id)
        if not user:
            return {
                'success': False,
                'message': 'User does not exist.'
            }

        # Create force stop operation callback
        async def force_stop_operation():
            async with self._ui_lock:
                try:
                    if user.is_running:
                        self.whalesbot.stop(user.emulator_index)

                    user.status = InstanceStatus.STOPPED.value
                    user.last_stop = datetime.now(pytz.UTC).isoformat()
                    self.data_manager.save_user(user)

                    return {
                        'success': True,
                        'message': f'Force stopped bot for {user.discord_name}'
                    }

                except Exception as e:
                    return {
                        'success': False,
                        'message': f'Error: {str(e)}'
                    }

        # Add operation with CRITICAL priority
        operation_id = await self.operation_queue.add_operation(
            operation_type=OperationType.STOP,
            user_id=user_id,
            user_name=f"ADMIN:{user.discord_name}",
            emulator_index=user.emulator_index,
            priority=Priority.CRITICAL,
            timeout=30,
            callback=force_stop_operation,
            metadata={'force_stop': True, 'admin_operation': True}
        )

        # Wait for operation to complete
        result = await self.operation_queue.wait_for_operation(operation_id, timeout=60)

        if result is None:
            return {
                'success': False,
                'message': 'Force stop operation timed out.'
            }

        if result.status == OperationStatus.COMPLETED:
            return result.result or {'success': False, 'message': 'Unknown error'}
        else:
            return {
                'success': False,
                'message': f'Force stop failed: {result.error or "Unknown error"}'
            }

    def get_queue_info(self) -> Dict[str, Any]:
        """
        Get queue information for admin monitoring.

        Returns:
            Queue information dictionary
        """
        return self.operation_queue.get_queue_info()

    def get_pending_operations(self, limit: int = 20) -> list:
        """
        Get list of pending operations for admin monitoring.

        Args:
            limit: Maximum number of operations to return

        Returns:
            List of pending operations
        """
        return self.operation_queue.get_pending_operations(limit)

    async def cancel_user_operation(self, user_id: str) -> Dict[str, Any]:
        """
        Cancel pending operation for a user.

        Args:
            user_id: Discord user ID

        Returns:
            Result dictionary
        """
        user = self.data_manager.get_user(user_id)
        if not user:
            return {
                'success': False,
                'message': 'User not found.'
            }

        # Find user's pending operations
        pending_ops = self.operation_queue.get_pending_operations()
        user_ops = [op for op in pending_ops if op['user_name'] == user.discord_name]

        if not user_ops:
            return {
                'success': False,
                'message': 'No pending operations found for this user.'
            }

        # Cancel the first pending operation
        operation_id = user_ops[0]['operation_id']
        cancelled = self.operation_queue.cancel_operation(operation_id)

        if cancelled:
            return {
                'success': True,
                'message': f'Cancelled pending {user_ops[0]["operation_type"]} operation for {user.discord_name}.'
            }
        else:
            return {
                'success': False,
                'message': 'Could not cancel operation (may already be processing).'
            }

    def get_available_emulators(self) -> Dict[str, Any]:
        """
        Get list of all available emulators (non-blocking).

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

            # Find linked users
            all_users = self.data_manager.get_all_users()
            for user in all_users:
                for emu in emulators:
                    if user.emulator_index == emu['index']:
                        emu['linked_user'] = user.discord_name

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

    async def cleanup(self) -> None:
        """Cleanup resources."""
        await self.operation_queue.stop_processor()
        if self._whalesbot:
            self._whalesbot.cleanup()
            self._whalesbot = None