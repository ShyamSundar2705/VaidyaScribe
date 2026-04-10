#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# VaidyaScribe — EC2 setup script
# Run this ONCE after SSH-ing into a fresh Amazon Linux 2023 / Ubuntu 22.04 instance
#
# EC2: t2.micro (free tier — 1 vCPU, 1GB RAM)
# ─────────────────────────────────────────────────────────────────
set -e

echo "=== VaidyaScribe EC2 Setup ==="

# ─── 1. System packages ───────────────────────────────────────────
echo "[1/6] Installing system packages..."
if command -v dnf &>/dev/null; then
    # Amazon Linux 2023
    sudo dnf update -y
    sudo dnf install -y docker git
    sudo dnf install -y python3-pip
else
    # Ubuntu 22.04
    sudo apt-get update -y
    sudo apt-get install -y docker.io docker-compose-plugin git python3-pip
fi

# ─── 2. Docker ────────────────────────────────────────────────────
echo "[2/6] Starting Docker..."
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

# Install Docker Compose v2
DOCKER_COMPOSE_VERSION="2.24.5"
sudo mkdir -p /usr/local/lib/docker/cli-plugins
sudo curl -SL "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-linux-x86_64" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
echo "Docker Compose: $(docker compose version)"

# ─── 3. Clone repo ────────────────────────────────────────────────
echo "[3/6] Cloning repository..."
cd /home/ec2-user 2>/dev/null || cd /home/ubuntu
git clone https://github.com/YOUR_USERNAME/vaidyascribe.git
cd vaidyascribe

# ─── 4. Environment file ──────────────────────────────────────────
echo "[4/6] Creating .env file..."
cp .env.example .env

echo ""
echo ">>> IMPORTANT: Edit .env now with your values:"
echo "    nano .env"
echo ""
echo "    Required for production:"
echo "    - SECRET_KEY  (generate: python3 -c \"import secrets; print(secrets.token_hex(32))\")"
echo "    - GROQ_API_KEY (free at console.groq.com)"
echo "    - DATABASE_URL (RDS endpoint if using PostgreSQL)"
echo "    - AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY + S3_BUCKET_NAME (if using S3)"
echo ""
read -p "Press ENTER after editing .env to continue..."

# ─── 5. Build and start ───────────────────────────────────────────
echo "[5/6] Building and starting services..."
# Pull Ollama model before starting (do this in background)
newgrp docker << 'INNEREOF'
docker compose pull redis nginx
docker compose build backend frontend
docker compose up -d

# Wait for backend to be ready
echo "Waiting for backend..."
for i in $(seq 1 30); do
    if curl -sf http://localhost/health > /dev/null 2>&1; then
        echo "Backend ready!"
        break
    fi
    echo "  attempt $i/30..."
    sleep 5
done

# ─── 6. Seed demo data ────────────────────────────────────────────
echo "[6/6] Seeding demo data..."
docker compose exec -T backend python scripts/seed_demo.py || echo "Seed skipped (DB may already have data)"
INNEREOF

echo ""
echo "=== Setup complete ==="
echo ""
echo "VaidyaScribe is running at: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)"
echo ""
echo "Next steps:"
echo "  1. In AWS Console → EC2 → Security Groups:"
echo "     Add inbound rule: HTTP (port 80) from Anywhere (0.0.0.0/0)"
echo "  2. Pull Ollama model (takes ~5 min, runs in background):"
echo "     docker compose exec ollama ollama pull llama3.2:3b"
echo "  3. Access the app at the URL above"
