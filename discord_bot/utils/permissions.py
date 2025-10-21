"""
Permission checking utilities for Discord bot.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
import pytz
import discord

from shared.data_manager import DataManager


class PermissionChecker:
    """Check permissions for Discord commands."""
    
    def __init__(self, data_manager: DataManager):
        """
        Initialize permission checker.
        
        Args:
            data_manager: Data manager instance
        """
        self.data_manager = data_manager
        self._cooldowns: Dict[str, datetime] = {}
    
    def is_admin(self, ctx: discord.ApplicationContext) -> bool:
        """
        Check if user is admin.
        
        Args:
            ctx: Discord application context
            
        Returns:
            True if user is admin
        """
        config = self.data_manager.get_config()
        
        # Check if user ID is in admin users list
        if str(ctx.author.id) in config.admin_users:
            return True
        
        # Check if user is server owner
        if ctx.guild and ctx.author.id == ctx.guild.owner_id:
            return True
        
        # Check if user has admin role
        if ctx.guild and hasattr(ctx.author, 'roles'):
            user_role_ids = [str(role.id) for role in ctx.author.roles]
            if any(role_id in config.admin_roles for role_id in user_role_ids):
                return True
        
        return False
    
    def in_allowed_location(self, ctx: discord.ApplicationContext) -> tuple[bool, Optional[str]]:
        """
        Check if command is in allowed guild/channel.
        
        Args:
            ctx: Discord application context
            
        Returns:
            Tuple of (is_allowed, error_message)
        """
        config = self.data_manager.get_config()
        
        # If no restrictions set, allow everywhere
        if not config.allowed_guilds and not config.allowed_channels:
            return True, None
        
        # Check guild
        if config.allowed_guilds:
            if not ctx.guild:
                return False, "❌ Lệnh này chỉ có thể dùng trong server được phép."
            
            if str(ctx.guild.id) not in config.allowed_guilds:
                return False, "This server is not allowed to use the bot."
        
        # Check channel
        if config.allowed_channels:
            if str(ctx.channel.id) not in config.allowed_channels:
                return False, "This channel is not allowed to use the bot."
        
        return True, None
    
    def check_cooldown(self, user_id: str, cooldown_seconds: Optional[int] = None) -> tuple[bool, Optional[str]]:
        """
        Check if user is on cooldown.
        
        Args:
            user_id: Discord user ID
            cooldown_seconds: Cooldown duration (uses config if None)
            
        Returns:
            Tuple of (can_proceed, error_message)
        """
        if cooldown_seconds is None:
            config = self.data_manager.get_config()
            cooldown_seconds = config.cooldown_seconds
        
        if cooldown_seconds <= 0:
            return True, None
        
        now = datetime.now(pytz.UTC)
        
        if user_id in self._cooldowns:
            last_use = self._cooldowns[user_id]
            time_passed = (now - last_use).total_seconds()
            
            if time_passed < cooldown_seconds:
                remaining = int(cooldown_seconds - time_passed)
                return False, f"⏳ "
                return False, f"⏳ Please wait for {remaining} more seconds before trying again."
        
        # Update cooldown
        self._cooldowns[user_id] = now
        
        # Cleanup old entries (older than 1 hour)
        cutoff = now - timedelta(hours=1)
        self._cooldowns = {
            uid: timestamp
            for uid, timestamp in self._cooldowns.items()
            if timestamp > cutoff
        }
        
        return True, None


# Global instance (will be set by bot)
_permission_checker: Optional[PermissionChecker] = None


def init_permission_checker(data_manager: DataManager) -> None:
    """
    Initialize global permission checker.
    
    Args:
        data_manager: Data manager instance
    """
    global _permission_checker
    _permission_checker = PermissionChecker(data_manager)


def get_permission_checker() -> PermissionChecker:
    """Get global permission checker instance."""
    if _permission_checker is None:
        raise RuntimeError("Permission checker not initialized")
    return _permission_checker


def is_admin(ctx: discord.ApplicationContext) -> bool:
    """
    Check if user is admin.
    
    Args:
        ctx: Discord application context
        
    Returns:
        True if user is admin
    """
    return get_permission_checker().is_admin(ctx)


def in_allowed_channel(ctx: discord.ApplicationContext) -> tuple[bool, Optional[str]]:
    """
    Check if command is in allowed location.
    
    Args:
        ctx: Discord application context
        
    Returns:
        Tuple of (is_allowed, error_message)
    """
    return get_permission_checker().in_allowed_location(ctx)


def check_cooldown(user_id: str, cooldown_seconds: Optional[int] = None) -> tuple[bool, Optional[str]]:
    """
    Check if user is on cooldown.
    
    Args:
        user_id: Discord user ID
        cooldown_seconds: Cooldown duration (uses config if None)
        
    Returns:
        Tuple of (can_proceed, error_message)
    """
    return get_permission_checker().check_cooldown(user_id, cooldown_seconds)

