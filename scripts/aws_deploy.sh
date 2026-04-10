#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# VaidyaScribe — deploy update to EC2
# Run from your LOCAL machine to push code changes to EC2
#
# Usage: ./scripts/aws_deploy.sh <ec2-public-ip>
# Example: ./scripts/aws_deploy.sh 13.235.12.45
# ─────────────────────────────────────────────────────────────────
set -e

EC2_IP="${1:?Usage: $0 <ec2-public-ip>}"
EC2_USER="ec2-user"   # Amazon Linux 2023
KEY_FILE="~/.ssh/vaidyascribe-key.pem"

echo "=== Deploying to EC2: $EC2_IP ==="

ssh -i "$KEY_FILE" "$EC2_USER@$EC2_IP" << 'REMOTE'
  cd ~/vaidyascribe
  git pull origin main
  docker compose build backend frontend
  docker compose up -d --force-recreate backend frontend nginx
  echo "Deploy complete. Health check:"
  curl -sf http://localhost/health && echo " ✓ Backend healthy"
REMOTE

echo "=== Deployed ==="
echo "App: http://$EC2_IP"
