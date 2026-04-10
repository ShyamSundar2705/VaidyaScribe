#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# Creates AWS resources using AWS CLI (free tier only)
# Run this ONCE from your local machine (not the EC2 instance)
#
# Prerequisites:
#   aws configure   (set your AWS credentials)
# ─────────────────────────────────────────────────────────────────
set -e

REGION="ap-south-1"
BUCKET_NAME="vaidyascribe-exports-$(date +%s)"   # unique name
DB_IDENTIFIER="vaidyascribe-db"
DB_NAME="vaidyascribe"
DB_USER="vaidyascribe"
DB_PASSWORD="$(python -c 'import secrets; print(secrets.token_hex(16))')"

echo "=== Creating VaidyaScribe AWS resources (free tier) ==="
echo "Region: $REGION"
echo ""

# ─── S3 Bucket ────────────────────────────────────────────────────
echo "[1/4] Creating S3 bucket: $BUCKET_NAME"
aws s3 mb "s3://$BUCKET_NAME" --region "$REGION"

# Block all public access (HIPAA best practice)
aws s3api put-public-access-block \
    --bucket "$BUCKET_NAME" \
    --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# Enable server-side encryption
aws s3api put-bucket-encryption \
    --bucket "$BUCKET_NAME" \
    --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

echo "✓ S3 bucket created: $BUCKET_NAME"

# ─── RDS PostgreSQL ───────────────────────────────────────────────
echo ""
echo "[2/4] Creating RDS PostgreSQL instance (db.t3.micro — free tier)..."
echo "      This takes ~5 minutes..."

aws rds create-db-instance \
    --db-instance-identifier "$DB_IDENTIFIER" \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --engine-version "16" \
    --master-username "$DB_USER" \
    --master-user-password "$DB_PASSWORD" \
    --db-name "$DB_NAME" \
    --allocated-storage 20 \
    --storage-type gp2 \
    --no-multi-az \
    --no-publicly-accessible \
    --backup-retention-period 1 \
    --region "$REGION" \
    --tags Key=Project,Value=VaidyaScribe

echo "✓ RDS instance creation started (will take ~5 min)"

# ─── IAM user for S3 access ───────────────────────────────────────
echo ""
echo "[3/4] Creating IAM user for S3 access..."
IAM_USER="vaidyascribe-s3"

aws iam create-user --user-name "$IAM_USER" 2>/dev/null || echo "User already exists"

aws iam put-user-policy \
    --user-name "$IAM_USER" \
    --policy-name "VaidyaScribeS3Policy" \
    --policy-document "{
        \"Version\": \"2012-10-17\",
        \"Statement\": [{
            \"Effect\": \"Allow\",
            \"Action\": [\"s3:GetObject\",\"s3:PutObject\",\"s3:DeleteObject\",\"s3:ListBucket\"],
            \"Resource\": [
                \"arn:aws:s3:::$BUCKET_NAME\",
                \"arn:aws:s3:::$BUCKET_NAME/*\"
            ]
        }]
    }"

ACCESS_KEY=$(aws iam create-access-key --user-name "$IAM_USER" --query 'AccessKey.[AccessKeyId,SecretAccessKey]' --output text)
AWS_KEY=$(echo "$ACCESS_KEY" | cut -f1)
AWS_SECRET=$(echo "$ACCESS_KEY" | cut -f2)

echo "✓ IAM user created"

# ─── Wait for RDS and get endpoint ───────────────────────────────
echo ""
echo "[4/4] Waiting for RDS to be available..."
aws rds wait db-instance-available --db-instance-identifier "$DB_IDENTIFIER" --region "$REGION"
RDS_ENDPOINT=$(aws rds describe-db-instances \
    --db-instance-identifier "$DB_IDENTIFIER" \
    --region "$REGION" \
    --query 'DBInstances[0].Endpoint.Address' \
    --output text)

echo "✓ RDS ready: $RDS_ENDPOINT"

# ─── Print .env values ────────────────────────────────────────────
echo ""
echo "============================================================"
echo " Add these to your .env file on the EC2 instance:"
echo "============================================================"
echo ""
echo "DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${RDS_ENDPOINT}:5432/${DB_NAME}"
echo "AWS_ACCESS_KEY_ID=${AWS_KEY}"
echo "AWS_SECRET_ACCESS_KEY=${AWS_SECRET}"
echo "AWS_REGION=${REGION}"
echo "S3_BUCKET_NAME=${BUCKET_NAME}"
echo ""
echo "IMPORTANT: Save these credentials — they won't be shown again!"
echo "============================================================"

# Save to a local file as backup
cat > ./aws_credentials_SAVE_THIS.txt << CREDEOF
DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${RDS_ENDPOINT}:5432/${DB_NAME}
AWS_ACCESS_KEY_ID=${AWS_KEY}
AWS_SECRET_ACCESS_KEY=${AWS_SECRET}
AWS_REGION=${REGION}
S3_BUCKET_NAME=${BUCKET_NAME}
CREDEOF
echo "Credentials also saved to: ./aws_credentials_SAVE_THIS.txt"
