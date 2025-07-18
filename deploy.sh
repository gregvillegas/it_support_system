#!/bin/bash

# IT Support System Deployment Script
# Run this on your production server

set -e  # Exit on any error

echo "🚀 Starting IT Support System Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   print_error "This script should not be run as root for security reasons"
   exit 1
fi

# Update system packages
print_status "Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install required system packages
print_status "Installing system dependencies..."
sudo apt install -y python3 python3-pip python3-venv nginx postgresql postgresql-contrib redis-server

# Install PostgreSQL
print_status "Setting up PostgreSQL..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user (you'll need to set passwords manually)
print_warning "Setting up database... You'll need to set the database password manually"
sudo -u postgres psql -c "CREATE DATABASE it_support_db;"
sudo -u postgres psql -c "CREATE USER it_support_user WITH PASSWORD 'your_secure_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE it_support_db TO it_support_user;"

# Setup project directory
PROJECT_DIR="/var/www/it_support_system"
print_status "Setting up project directory at $PROJECT_DIR"
sudo mkdir -p $PROJECT_DIR
sudo chown $USER:$USER $PROJECT_DIR

# Copy application files (assuming you're running this from the project directory)
print_status "Copying application files..."
cp -r . $PROJECT_DIR/
cd $PROJECT_DIR

# Create virtual environment
print_status "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
print_status "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p logs
mkdir -p media
mkdir -p staticfiles

# Set up environment file
print_status "Setting up environment configuration..."
if [ ! -f .env ]; then
    cp .env.example .env
    print_warning "Please edit .env file with your actual configuration values"
fi

# Run database migrations
print_status "Running database migrations..."
python manage.py migrate --settings=it_support_project.production_settings

# Collect static files
print_status "Collecting static files..."
python manage.py collectstatic --noinput --settings=it_support_project.production_settings

# Create superuser (optional)
print_status "Creating superuser..."
python manage.py createsuperuser --settings=it_support_project.production_settings

# Set proper permissions
print_status "Setting file permissions..."
sudo chown -R $USER:www-data $PROJECT_DIR
chmod -R 755 $PROJECT_DIR
chmod -R 775 $PROJECT_DIR/media
chmod -R 775 $PROJECT_DIR/logs

print_status "✅ Basic deployment complete!"
print_warning "Next steps:"
echo "1. Edit .env file with your actual configuration"
echo "2. Configure Nginx (see nginx.conf.example)"
echo "3. Set up Gunicorn service (see gunicorn.service.example)"
echo "4. Set up SSL certificate if needed"
echo "5. Configure firewall settings"
