#!/bin/bash

# BCF Events Monitor - Daily Cron Script
# This script runs the BCF events monitor and logs the output

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/daily_monitor_$(date +%Y%m%d).log"
DATA_DIR="$SCRIPT_DIR/data"

# Email configuration (optional)
# Set these environment variables to enable email notifications:
# export BCF_EMAIL_TO="your-email@example.com"
# export BCF_EMAIL_USERNAME="your-gmail@gmail.com"
# export BCF_EMAIL_PASSWORD="your-app-password"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to cleanup old logs (keep last 30 days)
cleanup_old_logs() {
    find "$LOG_DIR" -name "daily_monitor_*.log" -mtime +30 -delete 2>/dev/null || true
}

# Start logging
log "Starting BCF Events Monitor daily check"

# Change to script directory
cd "$SCRIPT_DIR"

# Check if Python script exists
if [ ! -f "bcf_monitor.py" ]; then
    log "ERROR: bcf_monitor.py not found in $SCRIPT_DIR"
    exit 1
fi

# Check if virtual environment exists (optional)
if [ -f "venv/bin/activate" ]; then
    log "Activating virtual environment"
    source venv/bin/activate
fi

# Run the monitor
log "Running BCF events monitor..."

# Build command - use config file if it exists, otherwise use environment variables
if [ -f "bcf_monitor_config.json" ]; then
    log "Using configuration file: bcf_monitor_config.json"
    MONITOR_CMD="python3 bcf_monitor.py"
else
    log "No configuration file found, using environment variables"
    MONITOR_CMD="python3 bcf_monitor.py --data-dir \"$DATA_DIR\""
    
    # Add email options if environment variables are set
    if [ -n "$BCF_EMAIL_TO" ] && [ -n "$BCF_EMAIL_USERNAME" ] && [ -n "$BCF_EMAIL_PASSWORD" ]; then
        log "Email notifications enabled for $BCF_EMAIL_TO"
        MONITOR_CMD="$MONITOR_CMD --email --email-to \"$BCF_EMAIL_TO\" --email-username \"$BCF_EMAIL_USERNAME\" --email-password \"$BCF_EMAIL_PASSWORD\" --email-only-changes"
        
        # Add optional email configuration
        if [ -n "$BCF_EMAIL_FROM" ]; then
            MONITOR_CMD="$MONITOR_CMD --email-from \"$BCF_EMAIL_FROM\""
        fi
        if [ -n "$BCF_EMAIL_SMTP_SERVER" ]; then
            MONITOR_CMD="$MONITOR_CMD --email-smtp-server \"$BCF_EMAIL_SMTP_SERVER\""
        fi
        if [ -n "$BCF_EMAIL_SMTP_PORT" ]; then
            MONITOR_CMD="$MONITOR_CMD --email-smtp-port \"$BCF_EMAIL_SMTP_PORT\""
        fi
    else
        log "Email notifications not configured (set BCF_EMAIL_TO, BCF_EMAIL_USERNAME, BCF_EMAIL_PASSWORD to enable)"
    fi
fi

if eval "$MONITOR_CMD" 2>&1 | tee -a "$LOG_FILE"; then
    log "BCF Events Monitor completed successfully"
    EXIT_CODE=0
else
    log "BCF Events Monitor completed with errors"
    EXIT_CODE=1
fi

# Cleanup old logs
cleanup_old_logs

# Log completion
log "Daily monitor script finished with exit code $EXIT_CODE"

# Optional: Send email notification if there were errors
if [ $EXIT_CODE -ne 0 ] && [ -n "$NOTIFICATION_EMAIL" ]; then
    log "Sending error notification to $NOTIFICATION_EMAIL"
    echo "BCF Events Monitor encountered errors on $(date)" | \
    mail -s "BCF Monitor Error" "$NOTIFICATION_EMAIL" 2>/dev/null || \
    log "WARNING: Failed to send email notification"
fi

exit $EXIT_CODE
