#!/bin/bash
################################################################################
# ModernizeIT API - Deployment Script
# Run this script AFTER 01_ec2_setup.sh
################################################################################

set -e  # Exit on any error

echo "================================"
echo "ModernizeIT API - Deployment"
echo "================================"
echo ""

# Variables
REPO_URL="https://github.com/YOUR_ORG/modernizeit-api.git"  # UPDATE THIS
APP_DIR="/var/modernizeit/modernizeit-api"
VENV_DIR="$APP_DIR/.venv"

# Check if running as ubuntu user
if [ "$USER" != "ubuntu" ]; then
    echo "❌ This script must be run as ubuntu user"
    exit 1
fi

# Check if Docker group is active (requires re-login after setup)
if ! groups | grep -q docker; then
    echo "❌ Docker group not active. Please log out and log back in."
    echo "Run: exit, then: ssh -i your-key.pem ubuntu@<ip>"
    exit 1
fi

echo "📂 Cloning repository..."
if [ -d "$APP_DIR" ]; then
    echo "⚠️  Directory already exists. Pulling latest changes..."
    cd "$APP_DIR"
    git pull
else
    echo "⚠️  UPDATE THE REPO_URL IN THIS SCRIPT FIRST!"
    echo "For now, we'll create the directory manually..."
    mkdir -p "$APP_DIR"
    cd "$APP_DIR"
    # git clone "$REPO_URL" .
fi

echo ""
echo "🐍 Creating Python virtual environment..."
python3 -m venv "$VENV_DIR"

echo "📦 Installing Python dependencies..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip

# Check if requirements.txt exists
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "⚠️  requirements.txt not found. Install manually:"
    echo "pip install fastapi uvicorn pydantic boto3 python-multipart"
fi

echo ""
echo "⚙️  Setting up environment configuration..."
if [ -f "deployment/.env.production.template" ]; then
    cp deployment/.env.production.template .env
    echo "✅ Created .env file from template"
    echo "⚠️  IMPORTANT: Edit .env file with your settings:"
    echo "    nano .env"
else
    echo "⚠️  No .env template found. Create .env manually."
fi

echo ""
echo "📁 Creating necessary directories..."
mkdir -p db
mkdir -p task_logs
mkdir -p aws_creds

echo ""
echo "🔧 Setting up systemd service..."
sudo cp deployment/modernizeit-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable modernizeit-api.service

echo ""
echo "🧪 Testing API..."
echo "Starting API in test mode (Ctrl+C to stop)..."
echo "Running: uvicorn main:app --host 0.0.0.0 --port 8000"
echo ""
echo "Press Ctrl+C after verifying it starts successfully"
echo ""

# Test run (will be killed with Ctrl+C)
uvicorn main:app --host 0.0.0.0 --port 8000 || true

echo ""
echo "================================"
echo "✅ Deployment Complete!"
echo "================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Edit environment file:"
echo "   nano /var/modernizeit/modernizeit-api/.env"
echo ""
echo "2. Configure AWS credentials (if not using IAM role):"
echo "   aws configure"
echo ""
echo "3. Start the service:"
echo "   sudo systemctl start modernizeit-api"
echo ""
echo "4. Check service status:"
echo "   sudo systemctl status modernizeit-api"
echo ""
echo "5. View logs:"
echo "   tail -f /var/log/modernizeit/api.log"
echo ""
echo "6. Test API endpoint:"
echo "   curl http://localhost:8000/health"
echo ""
