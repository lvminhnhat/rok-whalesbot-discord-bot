"""
Input validation utilities.
"""

from datetime import datetime
from typing import Optional


def validate_emulator_index(index: int, max_emulators: int = 20) -> tuple[bool, Optional[str]]:
    """
    Validate emulator index.
    
    Args:
        index: Emulator index to validate
        max_emulators: Maximum number of emulators
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(index, int):
        return False, "Emulator index must be an integer."
    
    if index < 0:
        return False, "Emulator index cannot be negative."
    
    if index >= max_emulators:
        return False, f"❌ Emulator index phải nhỏ hơn {max_emulators}."
    
    return True, None


def validate_days(days: int) -> tuple[bool, Optional[str]]:
    """
    Validate days parameter.
    
    Args:
        days: Number of days
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(days, int):
        return False, "❌ Số days phải là số nguyên."
    
    if days <= 0:
        return False, "❌ Số days phải lớn hơn 0."
    
    if days > 3650:  # ~10 years
        return False, "❌ Số days quá lớn (tối đa 3650 days)."
    
    return True, None


def validate_date(date_str: str) -> tuple[bool, Optional[str]]:
    """
    Validate date string in YYYY-MM-DD format.
    
    Args:
        date_str: Date string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True, None
    except ValueError:
        return False, "❌ Định dạng days không hợp lệ. Sử dụng: YYYY-MM-DD (ví dụ: 2025-12-31)"

