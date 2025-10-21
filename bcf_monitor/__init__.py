"""
BCF Events Monitor - A professional monitoring system for Boylston Chess Foundation events.

This package provides modular components for monitoring chess events, parsing participant data,
and sending email notifications.
"""

__version__ = "1.0.0"
__author__ = "BCF Events Monitor Team"

# Import main classes for easy access
from .config import Config
from .monitor import BCFMonitor
from .http_client import HTTPClient
from .parsers import EventParser, EntryListParser, DateParser
from .email_notifier import EmailNotifier

__all__ = [
    'Config',
    'BCFMonitor', 
    'HTTPClient',
    'EventParser',
    'EntryListParser', 
    'DateParser',
    'EmailNotifier'
]
