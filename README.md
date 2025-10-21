# BCF Events Monitor

A professional Python monitoring system for Boylston Chess Foundation events. The system has been refactored into a modular architecture for better maintainability, testability, and extensibility.

## Features

- **Event Discovery**: Automatically finds upcoming events from the BCF events page
- **Event Details**: Fetches detailed information from individual event pages
- **Entry List Monitoring**: Tracks participant registrations and withdrawals
- **Smart Date Parsing**: Handles single dates, ranges, and multiple day events automatically
- **Daily Summaries**: Provides detailed reports of changes for events within 1 week
- **Snapshot Management**: Stores daily snapshots and automatically cleans up expired events
- **Email Notifications**: Sends HTML and plain text email reports with participant changes
- **Modular Architecture**: Professional, maintainable codebase with clear separation of concerns
- **Automated Monitoring**: Includes cron script for daily automated checks

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd bcf-events-monitor
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Manual Execution

Run the monitor manually to check for updates:

```bash
# New modular version (recommended)
python3 bcf_monitor_main.py

# Legacy version (still supported)
python3 bcf_monitor.py
```

### Configuration File

The easiest way to configure the monitor is using a configuration file. Create one with:

```bash
# New modular version (recommended)
python3 bcf_monitor_main.py --create-config

# Legacy version
python3 bcf_monitor.py --create-config
```

This creates `bcf_monitor_config.json` with default settings. Edit the file to customize:

```json
{
  "data_dir": "./data",
  "days_before": 7,
  "include": "",
  "exclude": "",
  "debug": false,
  "email": {
    "enabled": true,
    "to": "your-email@example.com",
    "from": "your-gmail@gmail.com",
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "username": "your-gmail@gmail.com",
    "password": "your-app-password-here",
    "only_changes": true
  }
}
```

### Command Line Options

**Configuration Options:**
- `--config`: Configuration file path (default: `bcf_monitor_config.json`)
- `--create-config`: Create a default configuration file

**Monitoring Options:**
- `--data-dir`: Directory to store snapshots (default: `./data`)
- `--days-before`: Number of days before event to start monitoring (default: 7)
- `--include`: Comma-separated keywords to include in event names
- `--exclude`: Comma-separated keywords to exclude from event names
- `--debug`: Enable debug output

**Email Notification Options:**
- `--email`: Enable email notifications
- `--email-to`: Email address to send notifications to
- `--email-from`: Email address to send notifications from
- `--email-smtp-server`: SMTP server (default: smtp.gmail.com)
- `--email-smtp-port`: SMTP port (default: 587)
- `--email-username`: SMTP username
- `--email-password`: SMTP password
- `--email-only-changes`: Only send email when there are participant changes

Examples:

```bash
# Create and edit configuration file
python3 bcf_monitor_main.py --create-config
# Edit bcf_monitor_config.json with your settings

# Run with configuration file (recommended)
python3 bcf_monitor_main.py

# Override specific settings from command line
python3 bcf_monitor_main.py --days-before 3
python3 bcf_monitor_main.py --include "Open"
python3 bcf_monitor_main.py --exclude "Scholastic"

# Use different configuration file
python3 bcf_monitor_main.py --config my_config.json

# Enable email notifications (if not in config file)
python3 bcf_monitor_main.py --email --email-to your-email@example.com

# Email only when there are changes
python3 bcf_monitor_main.py --email-only-changes
```

### Email Notifications

The monitor can send email notifications when participant changes are detected. You can configure email settings in several ways:

#### Method 1: Command Line Arguments
```bash
# New modular version (recommended)
python3 bcf_monitor_main.py --email --email-to your-email@example.com --email-username your-gmail@gmail.com --email-password your-app-password

# Legacy version
python3 bcf_monitor.py --email --email-to your-email@example.com --email-username your-gmail@gmail.com --email-password your-app-password
```

#### Method 2: Environment Variables
Set these environment variables for automatic configuration:
```bash
export BCF_EMAIL_TO="your-email@example.com"
export BCF_EMAIL_FROM="your-gmail@gmail.com"
export BCF_EMAIL_USERNAME="your-gmail@gmail.com"
export BCF_EMAIL_PASSWORD="your-app-password"
export BCF_EMAIL_SMTP_SERVER="smtp.gmail.com"
export BCF_EMAIL_SMTP_PORT="587"

# New modular version (recommended)
python3 bcf_monitor_main.py --email

# Legacy version
python3 bcf_monitor.py --email
```

#### Gmail Setup
For Gmail, you'll need to:
1. Enable 2-factor authentication
2. Generate an "App Password" (not your regular password)
3. Use the app password in the configuration

#### Email Options
- `--email-only-changes`: Only send emails when there are actual participant changes
- `--email-smtp-server`: Use different SMTP server (default: smtp.gmail.com)
- `--email-smtp-port`: Use different port (default: 587)

### Automated Daily Monitoring

To set up automated daily monitoring, use the provided cron script:

1. Make the cron script executable:
```bash
chmod +x run_daily_monitor.sh
```

2. Add to your crontab to run daily at 9 AM:
```bash
crontab -e
```

Add this line:
```
0 9 * * * /path/to/bcf-events-monitor/run_daily_monitor.sh
```

Or to run at a different time, adjust the cron expression:
- `0 9 * * *` - Daily at 9:00 AM
- `0 18 * * *` - Daily at 6:00 PM
- `0 9 * * 1-5` - Weekdays only at 9:00 AM

## Output

The script provides detailed reports showing:

- Event name and date
- Current participant count
- New registrations (with ratings and sections)
- Withdrawals (with ratings and sections)
- Key event details (entry fee, time control, sections)
- Links to event details and entry lists

Example output:
```
BCF event updates (2025-10-21)
==================================================

📅 ALTO (At Least Twenty-One) - https://boylstonchess.org/events/1429/alto-at-least-twenty-one
   Date: 2025-10-26
   Participants: 1 (no changes)
   📝 Entry List: https://boylstonchess.org/tournament/entries/1429

📅 November Quads - https://boylstonchess.org/events/1428/november-quads
   Date: 2025-11-01
   Participants: 1 (+1 -0)
   ✅ New participants:
      • Jim Jin (unr)
   📝 Entry List: https://boylstonchess.org/tournament/entries/1428

📅 Weekend Tournament - https://boylstonchess.org/events/1430/weekend-tournament
   Date: 2025-10-25 to 2025-10-27
   Participants: 8 (+2 -1)
   ✅ New participants:
      • Alice Johnson (1650) [Open]
      • Bob Wilson (1420) [U1600]
   ❌ Withdrawn participants:
      • Charlie Brown (1580) [Open]
   📝 Entry List: https://boylstonchess.org/tournament/entries/1430

==================================================
```

### Multiple Date Events

The system handles various date formats automatically:

- **Single Date**: `2025-10-26`
- **Date Ranges**: `2025-10-25 to 2025-10-27` (shows start and end)
- **Multiple Days**: `2025-10-25, 2025-10-27` (comma-separated)
- **And-separated**: `2025-10-25 and 2025-10-27`
- **Range Format**: `October 25-27, 2025` (automatically expanded to all days)

The system intelligently parses and displays dates in the most readable format for each event type.

#### Date Parsing Examples

The system can handle various input formats and automatically converts them:

| Input Format | Parsed Result | Display Format |
|-------------|---------------|----------------|
| `January 15-17, 2024` | `2024-01-15, 2024-01-16, 2024-01-17` | `2025-01-15 to 2025-01-17` |
| `January 15, 17, 2024` | `2024-01-15, 2024-01-17` | `2025-01-15, 2025-01-17` |
| `January 15 and 17, 2024` | `2024-01-15, 2024-01-17` | `2025-01-15, 2025-01-17` |
| `January 15, 2024` | `2024-01-15` | `2025-01-15` |
| `2024-01-15` | `2024-01-15` | `2025-01-15` |

## Data Storage

The script stores daily snapshots in JSON format in the data directory. Each snapshot contains:

- Event information (ID, name, date, URLs)
- Event details (entry fee, time control, sections, etc.)
- Participant list with ratings and sections
- Timestamp of last check

Snapshots are automatically deleted after events have passed.

## Architecture

The BCF Events Monitor has been refactored into a professional modular architecture for better maintainability, testability, and extensibility.

### Benefits of the New Architecture

- **Modular Design**: Each component has a single, clear responsibility
- **Easy Testing**: Individual components can be unit tested in isolation
- **Better Maintainability**: Changes to one component don't affect others
- **Professional Structure**: Follows Python packaging best practices
- **Backward Compatibility**: All existing functionality preserved
- **Enhanced Error Handling**: Component-specific error handling and logging
- **Advanced Date Parsing**: Robust handling of complex date formats and ranges
- **Improved Email System**: Professional HTML and plain text email notifications

### Package Structure

```
bcf_monitor/                   # Main package directory
├── __init__.py               # Package initialization and exports
├── config.py                 # Configuration management
├── http_client.py            # HTTP client for web requests
├── parsers.py                # HTML parsing logic
├── email_notifier.py         # Email notification system
└── monitor.py                # Main monitoring orchestrator
```

### File Structure

```
bcf-events-monitor/
├── bcf_monitor_main.py        # New modular main script (recommended)
├── bcf_monitor.py             # Legacy script (backward compatibility)
├── bcf_monitor/               # Modular package directory
│   ├── __init__.py
│   ├── config.py
│   ├── http_client.py
│   ├── parsers.py
│   ├── email_notifier.py
│   └── monitor.py
├── run_daily_monitor.sh       # Cron script (auto-detects version)
├── requirements.txt           # Python dependencies
├── README.md                 # This file
├── REFACTORING_SUMMARY.md    # Detailed refactoring documentation
├── bcf_monitor_config.json   # Configuration file (created with --create-config)
├── config_example.json       # Example configuration file
├── email_config_example.sh   # Example email environment variables
├── crontab_example.txt       # Example crontab entries
└── data/                     # Snapshot storage directory (created automatically)
    ├── 1408.json            # Event snapshots
    └── 1405.json
```

## Dependencies

- `requests`: HTTP requests
- `beautifulsoup4`: HTML parsing
- `certifi`: SSL certificate verification

## Migration Guide

### From Legacy to Modular Version

The new modular system maintains 100% backward compatibility:

1. **Configuration**: Same configuration file format
2. **Command Line**: All existing arguments supported
3. **Output**: Identical console output format
4. **Data**: Existing snapshots and logs preserved

### Quick Migration Steps

1. **Test the new system**:
   ```bash
   python3 bcf_monitor_main.py --help
   ```

2. **Run with your existing configuration**:
   ```bash
   python3 bcf_monitor_main.py
   ```

3. **Update your cron jobs** (optional):
   ```bash
   # Old
   python3 bcf_monitor.py
   
   # New (recommended)
   python3 bcf_monitor_main.py
   ```

The shell script (`run_daily_monitor.sh`) automatically detects and uses the new version when available.

## Troubleshooting

### SSL Certificate Issues
If you encounter SSL certificate errors, the script includes fallback handling, but you can also run with:
```bash
# New modular version
python3 bcf_monitor_main.py --insecure

# Legacy version
python3 bcf_monitor.py --insecure
```

### Network Timeouts
The script uses a 20-second timeout for HTTP requests. If you experience timeouts, check your internet connection or the BCF website status.

### Permission Issues
Ensure the script has write permissions to the data directory:
```bash
chmod 755 data/
```

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is open source and available under the MIT License.