"""
Subscription management service.
"""

from datetime import datetime, timedelta
from typing import Optional, List
import pytz

from shared.models import User, Subscription
from shared.constants import InstanceStatus
from shared.data_manager import DataManager


class SubscriptionService:
    """Service for managing user subscriptions."""
    
    def __init__(self, data_manager: DataManager):
        """
        Initialize subscription service.
        
        Args:
            data_manager: Data manager instance
        """
        self.data_manager = data_manager
    
    def is_active(self, user_id: str) -> bool:
        """
        Check if user subscription is active.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            True if active, False otherwise
        """
        user = self.data_manager.get_user(user_id)
        if not user:
            return False
        return user.subscription.is_active
    
    def get_days_left(self, user_id: str) -> Optional[int]:
        """
        Get days left in subscription.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Days left or None if user not found
        """
        user = self.data_manager.get_user(user_id)
        if not user:
            return None
        return user.subscription.days_left
    
    def grant_subscription(
        self,
        discord_id: str,
        discord_name: str,
        days: int,
        emulator_index: Optional[int] = None
    ) -> dict:
        """
        Grant new subscription or extend existing one.
        
        Args:
            discord_id: Discord user ID
            discord_name: Discord username
            days: Number of days to grant
            emulator_index: Emulator index (required for new users)
            
        Returns:
            Result dictionary
        """
        user = self.data_manager.get_user(discord_id)
        
        if user:
            # Extend existing subscription
            return self.add_days(discord_id, days)
        else:
            # Create new user
            if emulator_index is None:
                return {
                    'success': False,
                    'message': '❌ Emulator index is required for new user'
                }
            
            # Check if emulator is already assigned
            if self.data_manager.is_emulator_assigned(emulator_index):
                return {
                    'success': False,
                    'message': f'❌ Emulator {emulator_index} đã được gán cho user khác'
                }
            
            now = datetime.now(pytz.UTC)
            end_date = now + timedelta(days=days)
            
            subscription = Subscription(
                start_at=now.isoformat(),
                end_at=end_date.isoformat()
            )
            
            new_user = User(
                discord_id=discord_id,
                discord_name=discord_name,
                emulator_index=emulator_index,
                subscription=subscription,
                status=InstanceStatus.STOPPED.value
            )
            
            self.data_manager.save_user(new_user)
            
            return {
                'success': True,
                'message': f'✅ Đã cấp {days} days cho {discord_name}\nEmulator: {emulator_index}\nExpires: {end_date.strftime("%Y-%m-%d")}'
            }
    
    def add_days(self, user_id: str, days: int) -> dict:
        """
        Add days to user subscription.
        
        Args:
            user_id: Discord user ID
            days: Number of days to add
            
        Returns:
            Result dictionary
        """
        user = self.data_manager.get_user(user_id)
        if not user:
            return {
                'success': False,
                'message': 'User does not exist'
            }
        
        # Calculate new end date
        current_end = user.subscription.end_datetime
        if current_end.tzinfo is None:
            current_end = pytz.UTC.localize(current_end)
        
        # If already expired, start from now
        now = datetime.now(pytz.UTC)
        if current_end < now:
            new_end = now + timedelta(days=days)
        else:
            new_end = current_end + timedelta(days=days)
        
        user.subscription.end_at = new_end.isoformat()
        self.data_manager.save_user(user)
        
        return {
            'success': True,
            'message': f'✅ Đã thêm {days} days cho {user.discord_name}\nNew expiry: {new_end.strftime("%Y-%m-%d")}\nTime left: {user.subscription.days_left} days'
        }
    
    def set_expiry(self, user_id: str, expiry_date: str) -> dict:
        """
        Set specific expiry date.
        
        Args:
            user_id: Discord user ID
            expiry_date: Expiry date in YYYY-MM-DD format
            
        Returns:
            Result dictionary
        """
        user = self.data_manager.get_user(user_id)
        if not user:
            return {
                'success': False,
                'message': 'User does not exist'
            }
        
        try:
            # Parse date
            expiry_dt = datetime.strptime(expiry_date, '%Y-%m-%d')
            expiry_dt = pytz.UTC.localize(expiry_dt.replace(hour=23, minute=59, second=59))
            
            user.subscription.end_at = expiry_dt.isoformat()
            self.data_manager.save_user(user)
            
            return {
                'success': True,
                'message': f'Set expiry for {user.discord_name}\nExpires: {expiry_date}\nTime left: {user.subscription.days_left} days'
            }
            
        except ValueError:
            return {
                'success': False,
                'message': '❌ Định dạng days không hợp lệ. Dùng: YYYY-MM-DD'
            }
    
    def revoke(self, user_id: str) -> dict:
        """
        Revoke user subscription.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            Result dictionary
        """
        user = self.data_manager.get_user(user_id)
        if not user:
            return {
                'success': False,
                'message': 'User does not exist'
            }
        
        # Set expiry to now
        now = datetime.now(pytz.UTC)
        user.subscription.end_at = now.isoformat()
        user.status = InstanceStatus.EXPIRED.value
        self.data_manager.save_user(user)
        
        return {
            'success': True,
            'message': f'Revoked access for {user.discord_name}'
        }
    
    def get_expiring_users(self, days: int = 7) -> List[User]:
        """
        Get users expiring within specified days.
        
        Args:
            days: Number of days threshold
            
        Returns:
            List of users expiring soon
        """
        return self.data_manager.get_expiring_users(days)
    
    def get_expired_users(self) -> List[User]:
        """
        Get expired users.
        
        Returns:
            List of expired users
        """
        return self.data_manager.get_expired_users()

