"""
Data models for the WhaleBots management system.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import pytz

from .constants import InstanceStatus, ActionType, ActionResult


@dataclass
class Subscription:
    """User subscription information."""
    start_at: str  # ISO format datetime
    end_at: str    # ISO format datetime
    
    @property
    def start_datetime(self) -> datetime:
        """Get start datetime object."""
        return datetime.fromisoformat(self.start_at)
    
    @property
    def end_datetime(self) -> datetime:
        """Get end datetime object."""
        return datetime.fromisoformat(self.end_at)
    
    @property
    def days_left(self) -> int:
        """Calculate days remaining."""
        now = datetime.now(pytz.UTC)
        end = self.end_datetime
        if end.tzinfo is None:
            end = pytz.UTC.localize(end)
        
        delta = end - now
        return max(0, delta.days)
    
    @property
    def is_active(self) -> bool:
        """Check if subscription is still active."""
        return self.days_left > 0
    
    @property
    def is_expired(self) -> bool:
        """Check if subscription has expired."""
        return self.days_left == 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'start_at': self.start_at,
            'end_at': self.end_at,
            'days_left': self.days_left,
            'is_active': self.is_active,
            'is_expired': self.is_expired
        }


@dataclass
class User:
    """User information and bot instance mapping."""
    discord_id: str
    discord_name: str
    emulator_index: int
    subscription: Subscription
    emulator_name: Optional[str] = None  # Emulator name (set via /link)
    status: str = InstanceStatus.STOPPED.value
    last_heartbeat: Optional[str] = None  # ISO format datetime
    created_at: str = field(default_factory=lambda: datetime.now(pytz.UTC).isoformat())
    last_start: Optional[str] = None  # ISO format datetime for cooldown
    last_stop: Optional[str] = None   # ISO format datetime
    
    @property
    def last_heartbeat_datetime(self) -> Optional[datetime]:
        """Get last heartbeat as datetime."""
        if self.last_heartbeat:
            return datetime.fromisoformat(self.last_heartbeat)
        return None
    
    @property
    def created_datetime(self) -> datetime:
        """Get created_at as datetime."""
        return datetime.fromisoformat(self.created_at)
    
    @property
    def last_start_datetime(self) -> Optional[datetime]:
        """Get last_start as datetime."""
        if self.last_start:
            return datetime.fromisoformat(self.last_start)
        return None
    
    @property
    def is_running(self) -> bool:
        """Check if instance is currently running."""
        return self.status == InstanceStatus.RUNNING.value
    
    @property
    def is_expired(self) -> bool:
        """Check if user subscription is expired."""
        return self.subscription.is_expired
    
    @property
    def uptime_seconds(self) -> Optional[int]:
        """Calculate uptime in seconds if running."""
        if self.is_running and self.last_start_datetime:
            now = datetime.now(pytz.UTC)
            start = self.last_start_datetime
            if start.tzinfo is None:
                start = pytz.UTC.localize(start)
            return int((now - start).total_seconds())
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'discord_id': self.discord_id,
            'discord_name': self.discord_name,
            'emulator_index': self.emulator_index,
            'emulator_name': self.emulator_name,
            'subscription': self.subscription.to_dict(),
            'status': self.status,
            'last_heartbeat': self.last_heartbeat,
            'created_at': self.created_at,
            'last_start': self.last_start,
            'last_stop': self.last_stop,
            'is_running': self.is_running,
            'uptime_seconds': self.uptime_seconds
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """Create User from dictionary."""
        subscription_data = data.get('subscription', {})
        subscription = Subscription(
            start_at=subscription_data.get('start_at', ''),
            end_at=subscription_data.get('end_at', '')
        )
        
        return cls(
            discord_id=data['discord_id'],
            discord_name=data['discord_name'],
            emulator_index=data['emulator_index'],
            subscription=subscription,
            emulator_name=data.get('emulator_name'),
            status=data.get('status', InstanceStatus.STOPPED.value),
            last_heartbeat=data.get('last_heartbeat'),
            created_at=data.get('created_at', datetime.now(pytz.UTC).isoformat()),
            last_start=data.get('last_start'),
            last_stop=data.get('last_stop')
        )


@dataclass
class BotConfig:
    """Bot configuration."""
    allowed_guilds: List[str] = field(default_factory=list)
    allowed_channels: List[str] = field(default_factory=list)
    admin_roles: List[str] = field(default_factory=list)
    admin_users: List[str] = field(default_factory=list)
    cooldown_seconds: int = 60
    max_emulators: int = 20
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BotConfig':
        """Create BotConfig from dictionary."""
        return cls(
            allowed_guilds=data.get('allowed_guilds', []),
            allowed_channels=data.get('allowed_channels', []),
            admin_roles=data.get('admin_roles', []),
            admin_users=data.get('admin_users', []),
            cooldown_seconds=data.get('cooldown_seconds', 60),
            max_emulators=data.get('max_emulators', 20)
        )


@dataclass
class AuditLog:
    """Audit log entry."""
    timestamp: str
    user_id: str
    user_name: str
    action: str
    details: str
    result: str
    performed_by: Optional[str] = None  # Admin user ID if action performed by admin
    
    @classmethod
    def create(
        cls,
        user_id: str,
        user_name: str,
        action: ActionType,
        details: str,
        result: ActionResult,
        performed_by: Optional[str] = None
    ) -> 'AuditLog':
        """Create a new audit log entry."""
        return cls(
            timestamp=datetime.now(pytz.UTC).isoformat(),
            user_id=user_id,
            user_name=user_name,
            action=action.value,
            details=details,
            result=result.value,
            performed_by=performed_by
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditLog':
        """Create AuditLog from dictionary."""
        return cls(**data)

