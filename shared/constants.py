"""
Constants and default values for the WhaleBots management system.
"""

from enum import Enum


class InstanceStatus(str, Enum):
    """Status of bot instance."""
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    EXPIRED = "EXPIRED"
    ERROR = "ERROR"


class ActionType(str, Enum):
    """Types of actions for audit logging."""
    START = "START"
    STOP = "STOP"
    GRANT = "GRANT"
    ADD_DAYS = "ADD_DAYS"
    SET_EXPIRY = "SET_EXPIRY"
    REVOKE = "REVOKE"
    CONFIG_CHANGE = "CONFIG_CHANGE"
    CONFIG_UPDATE = "CONFIG_UPDATE"
    FORCE_START = "FORCE_START"
    FORCE_STOP = "FORCE_STOP"


class ActionResult(str, Enum):
    """Result of an action."""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    DENIED = "DENIED"
    PARTIAL = "PARTIAL"


# Default configuration values
DEFAULT_COOLDOWN_SECONDS = 60
DEFAULT_MAX_EMULATORS = 20
DEFAULT_GRACE_PERIOD_DAYS = 3
DEFAULT_HEARTBEAT_TIMEOUT_SECONDS = 300  # 5 minutes

# Pagination
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100

# Expiry warnings
EXPIRY_WARNING_DAYS = [7, 3, 1]  # Warn at 7, 3, and 1 day before expiry

# Discord message settings
MAX_EMBED_FIELDS = 25
MAX_EMBED_DESCRIPTION_LENGTH = 4096

# File paths
DATA_DIR = "data"
USERS_FILE = "users.json"
CONFIG_FILE = "config.json"
AUDIT_LOGS_FILE = "audit_logs.json"

