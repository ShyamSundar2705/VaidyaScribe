# VaidyaScribe — AWS Free Tier Deployment Guide

Deploy VaidyaScribe to AWS using only free tier resources.
**Estimated monthly cost: $0** (within free tier limits)

---

## Free tier resources used

| Service | Tier | Limit |
|---------|------|-------|
| EC2 t2.micro | 750 hrs/month | Runs 24/7 for free |
| RDS db.t3.micro (PostgreSQL) | 750 hrs/month | One instance free |
| S3 | 5GB storage | PDF + FHIR exports |
| Data transfer | 1GB/month out | Sufficient for demo |

> **Note:** Free tier applies for the first 12 months of a new AWS account.

---

## Architecture on AWS

```
Internet
    │
    ▼
EC2 t2.micro (nginx:80)
    ├── frontend container  (React)
    ├── backend container   (FastAPI)
    ├── redis container     (session cache)
    └── ollama container    (local LLM)
         │
         ├── RDS PostgreSQL  (patient data)
         └── S3 bucket       (PDF + FHIR exports)
```

---

## Step 1 — Create EC2 instance

1. Go to **AWS Console → EC2 → Launch Instance**
2. Settings:
   - **Name:** vaidyascribe
   - **AMI:** Amazon Linux 2023 (free tier eligible)
   - **Instance type:** t2.micro ✓ free tier
   - **Key pair:** Create new → download `.pem` file → save as `vaidyascribe-key.pem`
   - **Security group:** Allow SSH (22) from your IP only
3. Click **Launch Instance**

### Open port 80 for the app

After launch:
1. EC2 → Instances → click your instance
2. Security tab → click the Security Group
3. Edit inbound rules → Add rule:
   - Type: HTTP
   - Port: 80
   - Source: Anywhere IPv4 (0.0.0.0/0)
4. Save

---

## Step 2 — Create AWS resources (S3 + RDS)

Run this from your **local machine** (requires AWS CLI configured):

```bash
# Install AWS CLI if needed
pip install awscli
aws configure   # enter your AWS access key, secret, region: ap-south-1

# Run the resource creation script
chmod +x scripts/aws_create_resources.sh
./scripts/aws_create_resources.sh
```

This creates:
- S3 bucket with encryption and private access
- RDS PostgreSQL db.t3.micro
- IAM user with minimal S3 permissions

**Save the output** — it contains your `DATABASE_URL`, S3 credentials.
They are also saved to `aws_credentials_SAVE_THIS.txt`.

---

## Step 3 — SSH into EC2 and run setup

```bash
# Fix key permissions (required by SSH)
chmod 400 vaidyascribe-key.pem

# SSH in (replace IP with your EC2 public IP)
ssh -i vaidyascribe-key.pem ec2-user@YOUR_EC2_IP

# On the EC2 instance, run the setup script
curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/vaidyascribe/main/scripts/aws_setup.sh | bash
```

When prompted to edit `.env`, add the values from Step 2:

```bash
nano .env
```

Key values to set:
```
SECRET_KEY=<generate: python3 -c "import secrets; print(secrets.token_hex(32))">
GROQ_API_KEY=gsk_...
DATABASE_URL=postgresql+asyncpg://vaidyascribe:password@your-rds.ap-south-1.rds.amazonaws.com:5432/vaidyascribe
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=ap-south-1
S3_BUCKET_NAME=vaidyascribe-exports-...
```

---

## Step 4 — Verify deployment

```bash
# Check all containers are running
docker compose ps

# Check health endpoint
curl http://localhost/health
# Expected: {"status":"ok","graph_ready":true}

# Get public IP
curl http://169.254.169.254/latest/meta-data/public-ipv4
```

Open `http://YOUR_EC2_IP` in your browser → you should see the login page.

---

## Step 5 — Pull Ollama model (background task)

```bash
# This runs in background — takes 5-10 min on t2.micro
docker compose exec ollama ollama pull llama3.2:3b &
echo "Model download started in background"
```

While waiting, the app works fine — SOAP generation falls back to Groq automatically.

---

## Deploying updates

From your local machine:

```bash
chmod +x scripts/aws_deploy.sh
./scripts/aws_deploy.sh YOUR_EC2_IP
```

This pulls the latest code, rebuilds changed containers, and restarts them.

---

## Cost monitoring

To make sure you stay in the free tier:

1. AWS Console → Billing → Free Tier Usage Alerts
2. Enable alerts for EC2, RDS, and S3
3. Set email notification at 80% usage

The app uses approximately:
- EC2: ~744 hrs/month (24/7) — exactly within 750hr limit
- RDS: ~744 hrs/month — exactly within 750hr limit  
- S3: ~50MB/month for typical demo usage — well within 5GB
- Data transfer: <100MB for demos — well within 1GB

---

## t2.micro memory management

t2.micro has only 1GB RAM. Ollama + backend together can exceed this.
If you see OOM kills:

```bash
# Limit Ollama memory in docker-compose.yml
# Add under ollama service:
#   mem_limit: 512m
#   memswap_limit: 512m

# Use the smaller model
docker compose exec ollama ollama pull llama3.2:1b
# Then update .env: OLLAMA_MODEL=llama3.2:1b
docker compose restart backend
```

For the demo, use `USE_GROQ_FALLBACK=true` in `.env` — then Ollama isn't needed at all and memory is fine.
