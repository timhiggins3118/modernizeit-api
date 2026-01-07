#!/bin/bash
################################################################################
# ModernizeIT API - EC2 Initial Setup Script
# Run this script on a fresh Ubuntu 24.04 LTS EC2 instance
################################################################################

set -e  # Exit on any error

echo "================================"
echo "ModernizeIT API - EC2 Setup"
echo "================================"
echo ""

# Update system packages
echo "📦 Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install Python 3.13 and pip
echo "🐍 Installing Python 3.13..."
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.13 python3.13-venv python3.13-dev python3-pip

# Set Python 3.13 as default
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.13 1
sudo update-alternatives --set python3 /usr/bin/python3.13

# Install pip for Python 3.13
echo "📦 Installing pip..."
curl -sS https://bootstrap.pypa.io/get-pip.py | sudo python3.13

# Install Docker
echo "🐳 Installing Docker..."
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io

# Add ubuntu user to docker group
sudo usermod -aG docker ubuntu

# Install docker-compose
echo "🐳 Installing docker-compose..."
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install AWS CLI
echo "☁️ Installing AWS CLI..."
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
sudo apt install -y unzip
unzip awscliv2.zip
sudo ./aws/install
rm -rf aws awscliv2.zip

# Install Git
echo "📚 Installing Git..."
sudo apt install -y git

# Install nginx (for future reverse proxy)
echo "🌐 Installing nginx..."
sudo apt install -y nginx

# Install other utilities
echo "🔧 Installing utilities..."
sudo apt install -y htop curl wget vim nano tree jq

# Create application directory
echo "📁 Creating application directory..."
sudo mkdir -p /var/modernizeit
sudo chown ubuntu:ubuntu /var/modernizeit

# Create logs directory
sudo mkdir -p /var/log/modernizeit
sudo chown ubuntu:ubuntu /var/log/modernizeit

# Verify installations
echo ""
echo "✅ Verifying installations..."
echo "Python version: $(python3 --version)"
echo "pip version: $(pip3 --version)"
echo "Docker version: $(docker --version)"
echo "docker-compose version: $(docker-compose --version)"
echo "AWS CLI version: $(aws --version)"
echo "Git version: $(git --version)"
echo "nginx version: $(nginx -v 2>&1)"

echo ""
echo "================================"
echo "✅ EC2 Setup Complete!"
echo "================================"
echo ""
echo "⚠️  IMPORTANT: Log out and log back in for Docker group changes to take effect"
echo ""
echo "Next steps:"
echo "1. Exit SSH: exit"
echo "2. Log back in: ssh -i your-key.pem ubuntu@<ip>"
echo "3. Run: 02_deploy_api.sh"
echo ""
