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
        self.data_manager = data_manager
    
    def is_admin(self, ctx: discord.ApplicationContext) -> bool:
        config = self.data_manager.get_config()
        
        if str(ctx.author.id) in config.admin_users:
            return True
        
        if ctx.guild and ctx.author.id == ctx.guild.owner_id:
            return True
        
        if ctx.guild and hasattr(ctx.author, 'roles'):
            user_role_ids = [str(role.id) for role in ctx.author.roles]
            if any(role_id in config.admin_roles for role_id in user_role_ids):
                return True
        
        return False
    
    def in_allowed_location(self, ctx: discord.ApplicationContext) -> tuple[bool, Optional[str]]:
        config = self.data_manager.get_config()
        
        if not config.allowed_guilds and not config.allowed_channels:
            return True, None
        
        if config.allowed_guilds:
            if not ctx.guild:
                return False, "This command can only be used in allowed servers."
            
            if str(ctx.guild.id) not in config.allowed_guilds:
                return False, "This server is not allowed to use the bot."
        
        if config.allowed_channels:
            if str(ctx.channel.id) not in config.allowed_channels:
                return False, "This channel is not allowed to use the bot."
        
        return True, None
    
    def check_cooldown(self, user_id: str, cooldown_seconds: Optional[int] = None) -> tuple[bool, Optional[str]]:
        if cooldown_seconds is None:
            config = self.data_manager.get_config()
            cooldown_seconds = config.cooldown_seconds
        
        if cooldown_seconds <= 0:
            return True, None
        
        now = datetime.now(pytz.UTC)
        
        last_use_str = self.data_manager.get_cooldown(user_id)
        if last_use_str:
            last_use = datetime.fromisoformat(last_use_str.replace('Z', '+00:00'))
            time_passed = (now - last_use).total_seconds()
            
            if time_passed < cooldown_seconds:
                remaining = int(cooldown_seconds - time_passed)
                return False, f"Please wait {remaining} more seconds before trying again."
        
        self.data_manager.set_cooldown(user_id, now.isoformat())
        self.data_manager.cleanup_cooldowns(max_age_hours=1)
        
        return True, None


_permission_checker: Optional[PermissionChecker] = None


def init_permission_checker(data_manager: DataManager) -> None:
    global _permission_checker
    _permission_checker = PermissionChecker(data_manager)


def get_permission_checker() -> PermissionChecker:
    if _permission_checker is None:
        raise RuntimeError("Permission checker not initialized")
    return _permission_checker


def is_admin(ctx: discord.ApplicationContext) -> bool:
    return get_permission_checker().is_admin(ctx)


def in_allowed_channel(ctx: discord.ApplicationContext) -> tuple[bool, Optional[str]]:
    return get_permission_checker().in_allowed_location(ctx)


def check_cooldown(user_id: str, cooldown_seconds: Optional[int] = None) -> tuple[bool, Optional[str]]:
    return get_permission_checker().check_cooldown(user_id, cooldown_seconds)

