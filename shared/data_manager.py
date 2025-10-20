"""
Thread-safe JSON data manager for persistent storage.
"""

import json
import os
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import pytz

from .models import User, BotConfig, AuditLog, Subscription
from .constants import (
    DATA_DIR, USERS_FILE, CONFIG_FILE, AUDIT_LOGS_FILE,
    InstanceStatus, ActionType, ActionResult
)


class DataManager:
    """Thread-safe JSON data manager."""
    
    def __init__(self, data_dir: str = DATA_DIR):
        """
        Initialize data manager.
        
        Args:
            data_dir: Directory for data files
        """
        self.data_dir = Path(data_dir)
        self.users_file = self.data_dir / USERS_FILE
        self.config_file = self.data_dir / CONFIG_FILE
        self.logs_file = self.data_dir / AUDIT_LOGS_FILE
        
        # Thread locks for file operations
        self._users_lock = threading.Lock()
        self._config_lock = threading.Lock()
        self._logs_lock = threading.Lock()
        
        # Ensure data directory and files exist
        self._initialize_files()
    
    def _initialize_files(self) -> None:
        """Create data directory and initialize files if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize users file
        if not self.users_file.exists():
            self._write_json(self.users_file, {"users": {}})
        
        # Initialize config file
        if not self.config_file.exists():
            default_config = BotConfig().to_dict()
            self._write_json(self.config_file, default_config)
        
        # Initialize logs file
        if not self.logs_file.exists():
            self._write_json(self.logs_file, {"logs": []})
    
    def _read_json(self, file_path: Path) -> Dict[str, Any]:
        """Read JSON file safely."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error reading {file_path}: {e}")
            return {}
    
    def _write_json(self, file_path: Path, data: Dict[str, Any]) -> None:
        """Write JSON file safely."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error writing {file_path}: {e}")
            raise
    
    # User operations
    
    def get_user(self, discord_id: str) -> Optional[User]:
        """
        Get user by Discord ID.
        
        Args:
            discord_id: Discord user ID
            
        Returns:
            User object or None if not found
        """
        with self._users_lock:
            data = self._read_json(self.users_file)
            users = data.get('users', {})
            
            if discord_id in users:
                return User.from_dict(users[discord_id])
            return None
    
    def save_user(self, user: User) -> None:
        """
        Save or update user.
        
        Args:
            user: User object to save
        """
        with self._users_lock:
            data = self._read_json(self.users_file)
            users = data.get('users', {})
            
            users[user.discord_id] = user.to_dict()
            data['users'] = users
            
            self._write_json(self.users_file, data)
    
    def delete_user(self, discord_id: str) -> bool:
        """
        Delete user.
        
        Args:
            discord_id: Discord user ID
            
        Returns:
            True if deleted, False if not found
        """
        with self._users_lock:
            data = self._read_json(self.users_file)
            users = data.get('users', {})
            
            if discord_id in users:
                del users[discord_id]
                data['users'] = users
                self._write_json(self.users_file, data)
                return True
            return False
    
    def get_all_users(self) -> List[User]:
        """
        Get all users.
        
        Returns:
            List of User objects
        """
        with self._users_lock:
            data = self._read_json(self.users_file)
            users = data.get('users', {})
            
            return [User.from_dict(user_data) for user_data in users.values()]
    
    def get_users_by_status(self, status: InstanceStatus) -> List[User]:
        """
        Get users by status.
        
        Args:
            status: Instance status to filter by
            
        Returns:
            List of User objects with matching status
        """
        all_users = self.get_all_users()
        return [user for user in all_users if user.status == status.value]
    
    def get_expiring_users(self, days: int = 7) -> List[User]:
        """
        Get users expiring within specified days.
        
        Args:
            days: Number of days threshold
            
        Returns:
            List of User objects expiring soon
        """
        all_users = self.get_all_users()
        return [
            user for user in all_users
            if 0 < user.subscription.days_left <= days
        ]
    
    def get_expired_users(self) -> List[User]:
        """
        Get expired users.
        
        Returns:
            List of User objects with expired subscriptions
        """
        all_users = self.get_all_users()
        return [user for user in all_users if user.subscription.is_expired]
    
    def get_user_by_emulator_index(self, emulator_index: int) -> Optional[User]:
        """
        Get user by emulator index.
        
        Args:
            emulator_index: Emulator index
            
        Returns:
            User object or None if not found
        """
        all_users = self.get_all_users()
        for user in all_users:
            if user.emulator_index == emulator_index:
                return user
        return None
    
    def is_emulator_assigned(self, emulator_index: int) -> bool:
        """
        Check if emulator index is already assigned.
        
        Args:
            emulator_index: Emulator index to check
            
        Returns:
            True if assigned, False otherwise
        """
        return self.get_user_by_emulator_index(emulator_index) is not None
    
    # Config operations
    
    def get_config(self) -> BotConfig:
        """
        Get bot configuration.
        
        Returns:
            BotConfig object
        """
        with self._config_lock:
            data = self._read_json(self.config_file)
            return BotConfig.from_dict(data)
    
    def save_config(self, config: BotConfig) -> None:
        """
        Save bot configuration.
        
        Args:
            config: BotConfig object to save
        """
        with self._config_lock:
            self._write_json(self.config_file, config.to_dict())
    
    def update_config(self, **kwargs) -> BotConfig:
        """
        Update specific config fields.
        
        Args:
            **kwargs: Fields to update
            
        Returns:
            Updated BotConfig object
        """
        config = self.get_config()
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
        self.save_config(config)
        return config
    
    # Audit log operations
    
    def log_action(
        self,
        user_id: str,
        user_name: str,
        action: ActionType,
        details: str,
        result: ActionResult,
        performed_by: Optional[str] = None
    ) -> None:
        """
        Log an action to audit logs.
        
        Args:
            user_id: Discord user ID
            user_name: Discord username
            action: Action type
            details: Action details
            result: Action result
            performed_by: Admin user ID if action performed by admin
        """
        log_entry = AuditLog.create(
            user_id=user_id,
            user_name=user_name,
            action=action,
            details=details,
            result=result,
            performed_by=performed_by
        )
        
        with self._logs_lock:
            data = self._read_json(self.logs_file)
            logs = data.get('logs', [])
            
            logs.insert(0, log_entry.to_dict())  # Add to beginning
            
            # Keep only last 10000 logs
            logs = logs[:10000]
            
            data['logs'] = logs
            self._write_json(self.logs_file, data)
    
    def get_logs(
        self,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[AuditLog]:
        """
        Get audit logs.
        
        Args:
            user_id: Filter by user ID (optional)
            limit: Maximum number of logs to return
            offset: Offset for pagination
            
        Returns:
            List of AuditLog objects
        """
        with self._logs_lock:
            data = self._read_json(self.logs_file)
            logs = data.get('logs', [])
            
            # Filter by user if specified
            if user_id:
                logs = [log for log in logs if log.get('user_id') == user_id]
            
            # Apply pagination
            logs = logs[offset:offset + limit]
            
            return [AuditLog.from_dict(log) for log in logs]
    
    def get_logs_count(self, user_id: Optional[str] = None) -> int:
        """
        Get total count of logs.
        
        Args:
            user_id: Filter by user ID (optional)
            
        Returns:
            Total count of logs
        """
        with self._logs_lock:
            data = self._read_json(self.logs_file)
            logs = data.get('logs', [])
            
            if user_id:
                logs = [log for log in logs if log.get('user_id') == user_id]
            
            return len(logs)

