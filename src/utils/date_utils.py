"""
Date utility functions for the crawler
"""

from datetime import datetime, timedelta


def get_yesterday() -> str:
    """
    Return yesterday's date as YYYY-MM-DD string.

    Returns:
        str: Yesterday's date in YYYY-MM-DD format
    """
    return (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')


def get_days_ago(days: int) -> str:
    """
    Return date N days ago as YYYY-MM-DD string.

    Args:
        days: Number of days ago

    Returns:
        str: Date in YYYY-MM-DD format
    """
    return (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')


def get_today() -> str:
    """
    Return today's date as YYYY-MM-DD string.

    Returns:
        str: Today's date in YYYY-MM-DD format
    """
    return datetime.now().strftime('%Y-%m-%d')


def format_date_for_input(date_str: str) -> str:
    """
    Convert YYYY-MM-DD to YYYY/MM/DD format for input fields.

    Args:
        date_str: Date string in YYYY-MM-DD format

    Returns:
        str: Date string in YYYY/MM/DD format
    """
    return date_str.replace('-', '/')


def validate_date(date_str: str) -> bool:
    """
    Validate date string format (YYYY-MM-DD).

    Args:
        date_str: Date string to validate

    Returns:
        bool: True if valid, False otherwise
    """
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False
