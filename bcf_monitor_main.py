#!/usr/bin/env python3
"""
BCF Events Monitor - Main Entry Point

A professional monitoring system for Boylston Chess Foundation events.
This script provides a clean command-line interface to the modular monitoring system.
"""

import argparse
import sys
from bcf_monitor import BCFMonitor
from bcf_monitor.config import Config


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser.
    
    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description="BCF Events Monitor - Professional monitoring system for chess events",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --create-config                    # Create default configuration file
  %(prog)s --config my_config.json           # Use custom configuration file
  %(prog)s --days-before 14 --email          # Monitor 14 days ahead with email
  %(prog)s --include "Tournament,Championship" # Only monitor specific events
  %(prog)s --exclude "Scholastics,Blitz"     # Exclude certain event types

Environment Variables:
  BCF_EMAIL_SMTP_SERVER    SMTP server for email notifications
  BCF_EMAIL_SMTP_PORT      SMTP port for email notifications  
  BCF_EMAIL_USERNAME       SMTP username for email notifications
  BCF_EMAIL_PASSWORD       SMTP password for email notifications
  BCF_EMAIL_FROM           From email address for notifications
  BCF_EMAIL_TO             Recipient email address for notifications
        """
    )
    
    # Configuration file options
    parser.add_argument(
        "--config", 
        default="bcf_monitor_config.json",
        help="Configuration file path (default: bcf_monitor_config.json)"
    )
    parser.add_argument(
        "--create-config", 
        action="store_true",
        help="Create a default configuration file and exit"
    )
    
    # Core monitoring options
    parser.add_argument(
        "--data-dir", 
        help="Directory to store event snapshots (overrides config file)"
    )
    parser.add_argument(
        "--days-before", 
        type=int,
        help="Number of days before event to start monitoring (overrides config file)"
    )
    parser.add_argument(
        "--include", 
        help="Comma-separated keywords that must be in event title (overrides config file)"
    )
    parser.add_argument(
        "--exclude", 
        help="Comma-separated keywords to exclude from event title (overrides config file)"
    )
    parser.add_argument(
        "--debug", 
        action="store_true",
        help="Enable debug output and save HTML files for troubleshooting"
    )
    
    # Email notification options
    parser.add_argument(
        "--email", 
        action="store_true",
        help="Enable email notifications (overrides config file)"
    )
    parser.add_argument(
        "--email-to", 
        help="Email address to send notifications to (overrides config file)"
    )
    parser.add_argument(
        "--email-from", 
        help="Email address to send notifications from (overrides config file)"
    )
    parser.add_argument(
        "--email-smtp-server", 
        help="SMTP server for email notifications (overrides config file)"
    )
    parser.add_argument(
        "--email-smtp-port", 
        type=int,
        help="SMTP port for email notifications (overrides config file)"
    )
    parser.add_argument(
        "--email-username", 
        help="SMTP username for email notifications (overrides config file)"
    )
    parser.add_argument(
        "--email-password", 
        help="SMTP password for email notifications (overrides config file)"
    )
    parser.add_argument(
        "--email-only-changes", 
        action="store_true",
        help="Only send email when there are participant changes (overrides config file)"
    )
    
    return parser


def apply_command_line_overrides(config: Config, args: argparse.Namespace) -> None:
    """Apply command line argument overrides to configuration.
    
    Args:
        config: Configuration object to modify
        args: Parsed command line arguments
    """
    # Core monitoring options
    if args.data_dir is not None:
        config.set("data_dir", args.data_dir)
    
    if args.days_before is not None:
        config.set("days_before", args.days_before)
    
    if args.include is not None:
        config.set("include", args.include)
    
    if args.exclude is not None:
        config.set("exclude", args.exclude)
    
    if args.debug:
        config.set("debug", True)
    
    # Email notification options
    if args.email:
        config.set("email.enabled", True)
    
    if args.email_to is not None:
        config.set("email.to", args.email_to)
    
    if args.email_from is not None:
        config.set("email.from", args.email_from)
    
    if args.email_smtp_server is not None:
        config.set("email.smtp_server", args.email_smtp_server)
    
    if args.email_smtp_port is not None:
        config.set("email.smtp_port", args.email_smtp_port)
    
    if args.email_username is not None:
        config.set("email.username", args.email_username)
    
    if args.email_password is not None:
        config.set("email.password", args.email_password)
    
    if args.email_only_changes:
        config.set("email.only_changes", True)


def validate_configuration(config: Config) -> None:
    """Validate configuration and exit with error if invalid.
    
    Args:
        config: Configuration object to validate
        
    Raises:
        SystemExit: If configuration is invalid
    """
    # Validate email configuration
    is_valid, error_message = config.validate_email_config()
    if not is_valid:
        print(f"[ERROR] {error_message}", file=sys.stderr)
        print("Use --email-to/--email-username/--email-password or set environment variables.", file=sys.stderr)
        sys.exit(1)


def main():
    """Main entry point for BCF Events Monitor."""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Handle config file creation
    if args.create_config:
        config = Config(args.config)
        if config.create_default_config():
            print(f"Default configuration file created: {args.config}")
            print("Please edit the file with your settings and remove the _comment and _instructions fields.")
        else:
            print(f"Failed to create configuration file: {args.config}")
            sys.exit(1)
        return
    
    # Load configuration
    config = Config(args.config)
    
    # Apply command line overrides
    apply_command_line_overrides(config, args)
    
    # Validate configuration
    validate_configuration(config)
    
    # Create and run monitor
    try:
        monitor = BCFMonitor(config)
        monitor.run()
    except KeyboardInterrupt:
        print("\n[INFO] Monitoring interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Monitoring failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
