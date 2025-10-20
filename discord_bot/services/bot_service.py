"""
Bot service for managing WhaleBots instances.
"""

import os
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


class BotService:
    """Service for managing bot instances via WhaleBots automation."""
    
    def __init__(self, whalebots_path: str, data_manager: DataManager):
        """
        Initialize bot service.
        
        Args:
            whalebots_path: Path to WhaleBots installation
            data_manager: Data manager instance
        """
        self.whalebots_path = whalebots_path
        self.data_manager = data_manager
        self._whalesbot: Optional[WhaleBots] = None
    
    @property
    def whalesbot(self) -> WhaleBots:
        """Get or create WhaleBots instance."""
        if self._whalesbot is None:
            self._whalesbot = WhaleBots(self.whalebots_path)
        return self._whalesbot
    
    def start_instance(self, user_id: str) -> Dict[str, Any]:
        """
        Start bot instance for user.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Result dictionary with success status and message
        """
        user = self.data_manager.get_user(user_id)
        if not user:
            return {
                'success': False,
                'message': "You don't have access. Please contact admin."
            }
        
        # Check if user is linked to an emulator
        if not user.emulator_name or user.emulator_index == -1:
            return {
                'success': False,
                'message': 'You are not linked to any emulator. Please use /link <emulator_name> to link first.\nUse /list_emulators to see available emulators.'
            }
        
        # Check subscription
        if user.subscription.is_expired:
            return {
                'success': False,
                'message': f'Your subscription expired on {user.subscription.end_at}. Please renew.'
            }
        
        # Check if already running
        if user.is_running:
            return {
                'success': False,
                'message': 'Your bot is already running.'
            }
        
        # Try to start
        try:
            self.whalesbot.start(user.emulator_index)
            
            # Update user status
            user.status = InstanceStatus.RUNNING.value
            user.last_start = datetime.now(pytz.UTC).isoformat()
            user.last_heartbeat = datetime.now(pytz.UTC).isoformat()
            self.data_manager.save_user(user)
            
            return {
                'success': True,
                'message': f'Bot started successfully!\nEmulator: {user.emulator_index}\nTime left: {user.subscription.days_left} days'
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
            
        except Exception as e:
            user.status = InstanceStatus.ERROR.value
            self.data_manager.save_user(user)
            return {
                'success': False,
                'message': f'Unknown error: {str(e)}'
            }
    
    def stop_instance(self, user_id: str) -> Dict[str, Any]:
        """
        Stop bot instance for user.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Result dictionary with success status and message
        """
        user = self.data_manager.get_user(user_id)
        if not user:
            return {
                'success': False,
                'message': "You don't have access."
            }
        
        # Check if running
        if not user.is_running:
            return {
                'success': False,
                'message': 'Your bot is not running.'
            }
        
        # Try to stop
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
                'message': f'Bot stopped successfully!{uptime_text}'
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
            
        except Exception as e:
            user.status = InstanceStatus.ERROR.value
            self.data_manager.save_user(user)
            return {
                'success': False,
                'message': f'Unknown error: {str(e)}'
            }
    
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
        
        # Build status message (text-only, no emojis)
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
            'days_left': user.subscription.days_left
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
    
    def force_stop_instance(self, user_id: str) -> Dict[str, Any]:
        """
        Force stop instance (for admin use).
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Result dictionary
        """
        user = self.data_manager.get_user(user_id)
        if not user:
            return {
                'success': False,
                'message': 'User does not exist.'
            }
        
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
                'message': f'❌ Lỗi: {str(e)}'
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
    
    def link_user_to_emulator(
        self,
        user_id: str,
        emulator_name: str,
        discord_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Link user to an emulator by name.
        Each emulator can only be linked to ONE user.
        
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
                'message': 'Please stop your bot before changing emulator link.'
            }
        
        # Find emulator by name
        try:
            emulator_state = self.whalesbot.get_emulator_state_by_name(emulator_name)
            if not emulator_state:
                return {
                    'success': False,
                    'message': f'Emulator "{emulator_name}" not found.'
                }
            
            # Check if emulator is already linked to another user
            all_users = self.data_manager.get_all_users()
            for other_user in all_users:
                if other_user.discord_id != user_id and other_user.emulator_index == emulator_state.index:
                    return {
                        'success': False,
                        'message': f'Emulator "{emulator_name}" is already linked to {other_user.discord_name}. Each emulator can only be linked to one user.'
                    }
            
            # Link emulator
            old_emulator = user.emulator_name or f"Unlinked (Index {user.emulator_index})"
            user.emulator_index = emulator_state.index
            user.emulator_name = emulator_state.emulator_info.name
            self.data_manager.save_user(user)
            
            return {
                'success': True,
                'message': f'Successfully linked to emulator "{emulator_name}"!\nOld: {old_emulator}\nNew: {user.emulator_name} (Index {user.emulator_index})'
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
                'message': 'Please stop your bot before unlinking emulator.'
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

    def cleanup(self) -> None:
        """Cleanup WhaleBots instance."""
        if self._whalesbot:
            self._whalesbot.cleanup()
            self._whalesbot = None
