"""
Utility functions for WhaleBots automation platform.

This module provides file I/O operations with caching, backup mechanisms,
security validation, and performance optimizations.
"""

import hashlib
import json
import os
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, Callable
import threading
from dataclasses import dataclass

try:
    from .config import FileConfiguration
    from .exceptions import (
        FileOperationError, SecurityError, ValidationError,
        handle_exception
    )
    from .logger import get_logger
except ImportError:
    # Fallback for running tests directly
    from whalebots_automation.config import FileConfiguration
    from whalebots_automation.exceptions import (
        FileOperationError, SecurityError, ValidationError,
        handle_exception
    )
    from whalebots_automation.logger import get_logger


@dataclass
class FileCacheEntry:
    """Cache entry for file data."""
    data: Any
    timestamp: float
    file_hash: str
    access_count: int = 0
    last_access: float = 0

    def is_valid(self, ttl_seconds: int) -> bool:
        """Check if cache entry is still valid."""
        return (time.time() - self.timestamp) < ttl_seconds

    def update_access(self) -> None:
        """Update access statistics."""
        self.access_count += 1
        self.last_access = time.time()


class FileCache:
    """
    Thread-safe file cache with TTL and LRU eviction.

    Provides caching for file operations to reduce disk I/O and improve
    performance for frequently accessed files.
    """

    def __init__(self, max_size: int = 100, default_ttl: int = 30):
        """
        Initialize file cache.

        Args:
            max_size: Maximum number of entries in cache
            default_ttl: Default TTL in seconds for cache entries
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, FileCacheEntry] = {}
        self._lock = threading.RLock()
        self.logger = get_logger(f"{__name__}.FileCache")

    def get(self, key: str) -> Optional[Any]:
        """
        Get data from cache.

        Args:
            key: Cache key (typically file path)

        Returns:
            Cached data or None if not found/expired
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None

            if not entry.is_valid(self.default_ttl):
                self.logger.debug(f"Cache entry expired: {key}")
                del self._cache[key]
                return None

            entry.update_access()
            self.logger.debug(f"Cache hit: {key}")
            return entry.data

    def put(self, key: str, data: Any, ttl: Optional[int] = None) -> None:
        """
        Put data into cache.

        Args:
            key: Cache key (typically file path)
            data: Data to cache
            ttl: Custom TTL in seconds (uses default if None)
        """
        with self._lock:
            # Calculate file hash for integrity checking
            file_hash = self._calculate_hash(data)

            # Create cache entry
            entry = FileCacheEntry(
                data=data,
                timestamp=time.time(),
                file_hash=file_hash
            )

            # Add to cache
            self._cache[key] = entry

            # Evict if necessary
            self._evict_if_needed()

            self.logger.debug(f"Data cached: {key}")

    def invalidate(self, key: str) -> None:
        """
        Invalidate a specific cache entry.

        Args:
            key: Cache key to invalidate
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self.logger.debug(f"Cache entry invalidated: {key}")

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self.logger.info(f"Cache cleared: {count} entries removed")

    def _evict_if_needed(self) -> None:
        """Evict oldest entries if cache is full."""
        while len(self._cache) > self.max_size:
            # Find least recently used entry
            lru_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].last_access
            )
            del self._cache[lru_key]
            self.logger.debug(f"Cache evicted: {lru_key}")

    @staticmethod
    def _calculate_hash(data: Any) -> str:
        """Calculate hash for data integrity checking."""
        if isinstance(data, (str, bytes)):
            content = data if isinstance(data, bytes) else data.encode('utf-8')
        else:
            content = json.dumps(data, sort_keys=True).encode('utf-8')

        return hashlib.sha256(content).hexdigest()


class BackupManager:
    """
    Manages backup creation and restoration for important files.

    Provides automatic backup functionality with rotation and integrity
    checking to prevent data loss during file operations.
    """

    def __init__(self, config: FileConfiguration):
        """
        Initialize backup manager.

        Args:
            config: File configuration settings
        """
        self.config = config
        self.logger = get_logger(f"{__name__}.BackupManager")

    def create_backup(self, file_path: str) -> Optional[str]:
        """
        Create a backup of the specified file.

        Args:
            file_path: Path to file to backup

        Returns:
            Path to backup file or None if backup failed

        Raises:
            FileOperationError: If backup operation fails
        """
        if not self.config.enable_backups:
            self.logger.debug(f"Backups disabled, skipping: {file_path}")
            return None

        if not os.path.exists(file_path):
            self.logger.warning(f"Cannot backup non-existent file: {file_path}")
            return None

        try:
            # Ensure backup directory exists
            os.makedirs(self.config.backup_path, exist_ok=True)

            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            backup_filename = f"{Path(file_path).stem}_{timestamp}{Path(file_path).suffix}"
            backup_path = os.path.join(self.config.backup_path, backup_filename)

            # Create backup
            shutil.copy2(file_path, backup_path)

            self.logger.info(f"Backup created: {file_path} -> {backup_path}")

            # Rotate old backups if necessary
            self._rotate_backups(file_path)

            return backup_path

        except Exception as e:
            raise FileOperationError(
                f"Failed to create backup for {file_path}: {e}",
                file_path=file_path,
                operation="backup"
            )

    def _rotate_backups(self, original_file_path: str) -> None:
        """
        Rotate old backups, keeping only the most recent ones.

        Args:
            original_file_path: Path to original file
        """
        try:
            original_filename = Path(original_file_path).stem

            # Find all backup files for this original file
            backup_files = []
            for filename in os.listdir(self.config.backup_path):
                if filename.startswith(f"{original_filename}_"):
                    backup_path = os.path.join(self.config.backup_path, filename)
                    backup_files.append((backup_path, os.path.getmtime(backup_path)))

            # Sort by modification time (newest first)
            backup_files.sort(key=lambda x: x[1], reverse=True)

            # Remove excess backups
            if len(backup_files) > self.config.max_backup_files:
                for backup_path, _ in backup_files[self.config.max_backup_files:]:
                    os.remove(backup_path)
                    self.logger.debug(f"Old backup removed: {backup_path}")

        except Exception as e:
            self.logger.warning(f"Failed to rotate backups: {e}")

    def list_backups(self, file_path: str) -> List[Tuple[str, datetime]]:
        """
        List all backups for a specific file.

        Args:
            file_path: Path to original file

        Returns:
            List of tuples (backup_path, creation_time)
        """
        if not os.path.exists(self.config.backup_path):
            return []

        original_filename = Path(file_path).stem
        backups = []

        try:
            for filename in os.listdir(self.config.backup_path):
                if filename.startswith(f"{original_filename}_"):
                    backup_path = os.path.join(self.config.backup_path, filename)
                    creation_time = datetime.fromtimestamp(os.path.getmtime(backup_path))
                    backups.append((backup_path, creation_time))

            # Sort by creation time (newest first)
            backups.sort(key=lambda x: x[1], reverse=True)

        except Exception as e:
            self.logger.error(f"Failed to list backups: {e}")

        return backups

    def restore_backup(self, file_path: str, backup_index: int = 0) -> bool:
        """
        Restore a backup of the specified file.

        Args:
            file_path: Path to file to restore
            backup_index: Index of backup to restore (0 = most recent)

        Returns:
            True if restore was successful, False otherwise
        """
        backups = self.list_backups(file_path)

        if backup_index >= len(backups):
            self.logger.error(f"Backup index {backup_index} out of range")
            return False

        backup_path = backups[backup_index][0]

        try:
            shutil.copy2(backup_path, file_path)
            self.logger.info(f"File restored from backup: {backup_path} -> {file_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to restore backup: {e}")
            return False


class SecureFileHandler:
    """
    Secure file handler with validation, caching, and backup functionality.

    Provides a secure interface for file operations with input validation,
    backup creation, and caching for performance.
    """

    def __init__(self, config: FileConfiguration):
        """
        Initialize secure file handler.

        Args:
            config: File configuration settings
        """
        self.config = config
        self.cache = FileCache() if config.enable_file_cache else None
        self.backup_manager = BackupManager(config)
        self.logger = get_logger(f"{__name__}.SecureFileHandler")

    @handle_exception
    def read_json(self, file_path: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """
        Read JSON file with security validation and caching.

        Args:
            file_path: Path to JSON file
            use_cache: Whether to use cached data if available

        Returns:
            Parsed JSON data or None if file doesn't exist

        Raises:
            FileOperationError: If read operation fails
            SecurityError: If file validation fails
        """
        # Normalize path
        file_path = os.path.abspath(file_path)

        # Check cache first
        if use_cache and self.cache:
            cached_data = self.cache.get(file_path)
            if cached_data is not None:
                self.logger.debug(f"Using cached data for: {file_path}")
                return cached_data

        # Validate file path
        self._validate_file_path(file_path)

        if not os.path.exists(file_path):
            self.logger.info(f"File does not exist: {file_path}")
            return None

        # Validate file size
        file_size = os.path.getsize(file_path)
        max_size_bytes = self.config.max_file_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            raise SecurityError(
                f"File too large: {file_size} bytes (max: {max_size_bytes} bytes)",
                file_path=file_path
            )

        try:
            with open(file_path, 'r', encoding=self.config.file_encoding) as f:
                data = json.load(f)

            # Validate JSON structure
            if not isinstance(data, (dict, list)):
                raise ValidationError("JSON file must contain object or array")

            # Cache the data
            if use_cache and self.cache:
                self.cache.put(file_path, data, ttl=self.config.cache_ttl_seconds)

            self.logger.debug(f"JSON file read successfully: {file_path}")
            return data

        except json.JSONDecodeError as e:
            raise FileOperationError(
                f"Invalid JSON in file {file_path}: {e}",
                file_path=file_path,
                operation="read"
            )
        except UnicodeDecodeError as e:
            raise FileOperationError(
                f"Encoding error in file {file_path}: {e}",
                file_path=file_path,
                operation="read"
            )

    @handle_exception
    def write_json(self, file_path: str, data: Any, create_backup: bool = True) -> bool:
        """
        Write JSON file with backup creation and validation.

        Args:
            file_path: Path to JSON file
            data: Data to write
            create_backup: Whether to create backup of existing file

        Returns:
            True if write was successful, False otherwise

        Raises:
            FileOperationError: If write operation fails
            SecurityError: If validation fails
        """
        # Normalize path
        file_path = os.path.abspath(file_path)

        # Validate file path
        self._validate_file_path(file_path)

        # Validate data
        if not isinstance(data, (dict, list)):
            raise ValidationError("Data must be JSON-serializable (dict or list)")

        # Create backup if file exists
        if create_backup and os.path.exists(file_path):
            self.backup_manager.create_backup(file_path)

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Write to temporary file first
            temp_file = file_path + '.tmp'
            with open(temp_file, 'w', encoding=self.config.file_encoding) as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Atomic move to final location
            if os.name == 'nt':  # Windows
                if os.path.exists(file_path):
                    os.remove(file_path)
            os.rename(temp_file, file_path)

            # Invalidate cache
            if self.cache:
                self.cache.invalidate(file_path)

            self.logger.debug(f"JSON file written successfully: {file_path}")
            return True

        except Exception as e:
            # Clean up temporary file if it exists
            temp_file = file_path + '.tmp'
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass

            raise FileOperationError(
                f"Failed to write JSON file {file_path}: {e}",
                file_path=file_path,
                operation="write"
            )

    @handle_exception
    def read_text(self, file_path: str, use_cache: bool = True) -> Optional[str]:
        """
        Read text file with security validation and caching.

        Args:
            file_path: Path to text file
            use_cache: Whether to use cached data if available

        Returns:
            File contents or None if file doesn't exist

        Raises:
            FileOperationError: If read operation fails
            SecurityError: If file validation fails
        """
        # Normalize path
        file_path = os.path.abspath(file_path)

        # Check cache first
        if use_cache and self.cache:
            cached_data = self.cache.get(file_path)
            if cached_data is not None:
                return cached_data

        # Validate file path
        self._validate_file_path(file_path)

        if not os.path.exists(file_path):
            self.logger.info(f"File does not exist: {file_path}")
            return None

        # Validate file size
        file_size = os.path.getsize(file_path)
        max_size_bytes = self.config.max_file_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            raise SecurityError(
                f"File too large: {file_size} bytes (max: {max_size_bytes} bytes)",
                file_path=file_path
            )

        try:
            with open(file_path, 'r', encoding=self.config.file_encoding) as f:
                data = f.read()

            # Cache the data
            if use_cache and self.cache:
                self.cache.put(file_path, data, ttl=self.config.cache_ttl_seconds)

            self.logger.debug(f"Text file read successfully: {file_path}")
            return data

        except UnicodeDecodeError as e:
            raise FileOperationError(
                f"Encoding error in file {file_path}: {e}",
                file_path=file_path,
                operation="read"
            )

    @handle_exception
    def write_text(self, file_path: str, data: str, create_backup: bool = True) -> bool:
        """
        Write text file with backup creation and validation.

        Args:
            file_path: Path to text file
            data: Text data to write
            create_backup: Whether to create backup of existing file

        Returns:
            True if write was successful, False otherwise

        Raises:
            FileOperationError: If write operation fails
            SecurityError: If validation fails
        """
        # Normalize path
        file_path = os.path.abspath(file_path)

        # Validate file path
        self._validate_file_path(file_path)

        # Validate data
        if not isinstance(data, str):
            raise ValidationError("Data must be a string")

        # Create backup if file exists
        if create_backup and os.path.exists(file_path):
            self.backup_manager.create_backup(file_path)

        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Write to temporary file first
            temp_file = file_path + '.tmp'
            with open(temp_file, 'w', encoding=self.config.file_encoding) as f:
                f.write(data)

            # Atomic move to final location
            if os.name == 'nt':  # Windows
                if os.path.exists(file_path):
                    os.remove(file_path)
            os.rename(temp_file, file_path)

            # Invalidate cache
            if self.cache:
                self.cache.invalidate(file_path)

            self.logger.debug(f"Text file written successfully: {file_path}")
            return True

        except Exception as e:
            # Clean up temporary file if it exists
            temp_file = file_path + '.tmp'
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass

            raise FileOperationError(
                f"Failed to write text file {file_path}: {e}",
                file_path=file_path,
                operation="write"
            )

    def _validate_file_path(self, file_path: str) -> None:
        """
        Validate file path for security.

        Args:
            file_path: File path to validate

        Raises:
            SecurityError: If path is invalid or suspicious
        """
        if not self.config.sanitize_file_paths:
            return

        # Check for path traversal attempts
        if '..' in file_path:
            raise SecurityError(
                f"Path traversal attempt detected: {file_path}",
                details={"file_path": file_path}
            )

        # Check for suspicious file extensions
        suspicious_extensions = ['.exe', '.bat', '.cmd', '.scr', '.vbs', '.js']
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext in suspicious_extensions:
            raise SecurityError(
                f"Suspicious file extension: {file_ext}",
                file_path=file_path
            )

    def invalidate_cache(self, file_path: Optional[str] = None) -> None:
        """
        Invalidate cache entries.

        Args:
            file_path: Specific file path to invalidate, or None to clear all
        """
        if self.cache:
            if file_path:
                self.cache.invalidate(os.path.abspath(file_path))
            else:
                self.cache.clear()