# AWS Infrastructure Setup (BE-025)

This document describes how to provision AWS resources for the production deployment.

## Resources Required

| Service | Purpose | Estimated Cost |
|---------|---------|---------------|
| ECS Fargate | Container hosting | ~$15/mo |
| RDS PostgreSQL (db.t4g.micro) | Database | ~$15/mo |
| S3 | Image storage | ~$5/mo |
| CloudFront | CDN (frontend) | ~$2/mo |
| Secrets Manager | API keys & DB password | ~$1/mo |
| CloudWatch | Logging & monitoring | ~$3/mo |

## Step 1: RDS PostgreSQL with PostGIS

```bash
aws rds create-db-instance \
  --db-instance-identifier disaster-assessment-db \
  --db-instance-class db.t4g.micro \
  --engine postgres \
  --engine-version 16.4 \
  --master-username dbadmin \
  --master-user-password $(aws secretsmanager get-random-password --query RandomPassword) \
  --allocated-storage 20 \
  --storage-type gp3 \
  --backup-retention-period 7 \
  --multi-az \
  --vpc-security-group-ids sg-xxxxxxxx \
  --db-subnet-group-name disaster-subnet-group
```

After RDS is up, enable PostGIS:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

Then run Alembic migrations:

```bash
DATABASE_URL=postgresql+asyncpg://dbadmin:PASSWORD@RDS_ENDPOINT:5432/postgres alembic upgrade head
```

## Step 2: S3 Bucket

```bash
aws s3 mb s3://disaster-assessment-images-prod --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket disaster-assessment-images-prod \
  --versioning-configuration Status=Enabled

# Lifecycle: move to Glacier after 90 days
aws s3api put-bucket-lifecycle-configuration \
  --bucket disaster-assessment-images-prod \
  --lifecycle-configuration file://s3-lifecycle.json
```

## Step 3: Secrets Manager

```bash
# Database password
aws secretsmanager create-secret \
  --name disaster-assessment/db-password \
  --secret-string "YOUR_DB_PASSWORD"

# JWT secret
aws secretsmanager create-secret \
  --name disaster-assessment/jwt-secret \
  --secret-string "$(openssl rand -base64 32)"

# Gemini API key (provided by ML teammate)
aws secretsmanager create-secret \
  --name disaster-assessment/gemini-api-key \
  --secret-string "GEMINI_API_KEY_HERE"
```

## Step 4: ECR Repository

```bash
aws ecr create-repository --repository-name disaster-assessment-backend
```

Get the login command:

```bash
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
```

## Step 5: ECS Cluster

```bash
aws ecs create-cluster --cluster-name disaster-assessment-cluster

# Register task definition
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json

# Create service
aws ecs create-service \
  --cluster disaster-assessment-cluster \
  --service-name disaster-api \
  --task-definition disaster-assessment-backend \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

## Step 6: CloudWatch Log Group

```bash
aws logs create-log-group --log-group-name /ecs/disaster-assessment-backend
aws logs put-retention-policy --log-group-name /ecs/disaster-assessment-backend --retention-in-days 14
```

## Verification Checklist

- [ ] RDS endpoint reachable from ECS security group only
- [ ] PostGIS extension enabled
- [ ] Alembic migrations applied
- [ ] S3 bucket created with versioning + lifecycle policy
- [ ] All secrets created in Secrets Manager
- [ ] ECR repository created
- [ ] ECS cluster + service running
- [ ] CloudWatch logs visible
- [ ] Health check passing on `/health`
