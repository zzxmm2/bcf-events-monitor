#!/bin/bash
# BCF Events Monitor - Email Configuration Example
# Copy this file and modify with your email settings

# Gmail Configuration Example
export BCF_EMAIL_TO="your-email@example.com"
export BCF_EMAIL_FROM="your-gmail@gmail.com"
export BCF_EMAIL_USERNAME="your-gmail@gmail.com"
export BCF_EMAIL_PASSWORD="your-app-password-here"
export BCF_EMAIL_SMTP_SERVER="smtp.gmail.com"
export BCF_EMAIL_SMTP_PORT="587"

# Other Email Providers Examples:

# Outlook/Hotmail
# export BCF_EMAIL_SMTP_SERVER="smtp-mail.outlook.com"
# export BCF_EMAIL_SMTP_PORT="587"

# Yahoo
# export BCF_EMAIL_SMTP_SERVER="smtp.mail.yahoo.com"
# export BCF_EMAIL_SMTP_PORT="587"

# Custom SMTP Server
# export BCF_EMAIL_SMTP_SERVER="mail.yourdomain.com"
# export BCF_EMAIL_SMTP_PORT="587"

echo "Email configuration loaded. You can now run:"
echo "python3 bcf_monitor.py --email --days-before 7"
echo ""
echo "Or use the cron script:"
echo "./run_daily_monitor.sh"
