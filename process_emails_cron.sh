#!/bin/bash
# Cron job script to process emails and create tickets
# Usage: Add this to your crontab to run every 5 minutes:
# */5 * * * * /path/to/it_support_system/process_emails_cron.sh

# Change to the project directory
cd /home/greg/it_support_system

# Activate virtual environment
source venv/bin/activate

# Run the email processing command
python manage.py process_emails

# Log the result with timestamp
echo "$(date): Email processing completed" >> /var/log/it_support_email_processing.log
