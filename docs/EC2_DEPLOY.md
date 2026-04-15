# EC2 Single-Instance Deployment Guide

A simple guide to deploy the entire backend stack on **one EC2 instance**. Total time: ~30 minutes.

## What This Sets Up

- One EC2 instance (Ubuntu 22.04) running:
  - PostgreSQL + PostGIS in Docker
  - FastAPI backend in Docker
  - Both managed by docker-compose
- Public IP accessible from the internet on port 8000
- Image storage on the instance's local disk (S3 fallback)

**Cost:** ~$15-30/month for a t3.small or t3.medium instance.

---

## Step 1: Launch an EC2 Instance

1. Sign in to AWS Console → **EC2** → **Launch instance**
2. Configure:
   - **Name:** `disaster-assessment-backend`
   - **AMI:** Ubuntu Server 22.04 LTS (free tier eligible)
   - **Instance type:** `t3.small` (2 vCPU, 2 GB) for demo / `t3.medium` (2 vCPU, 4 GB) recommended
   - **Key pair:** Create new key pair → name it `disaster-key` → download the `.pem` file (save it somewhere safe!)
   - **Network settings:**
     - ✓ Allow SSH traffic from: **My IP**
     - ✓ Allow HTTP traffic from internet
     - ✓ Allow HTTPS traffic from internet
   - **Storage:** 30 GB gp3 (default 8 GB is too small)
3. Click **Launch instance**
4. Wait ~1 minute for it to start, then copy the **Public IPv4 address** from the instance details

## Step 2: Open Port 8000 in Security Group

The default SG only allows 80/443. We need port 8000 too:

1. EC2 Console → **Security Groups**
2. Find the SG for your instance (usually starts with `launch-wizard-`)
3. **Edit inbound rules** → **Add rule**:
   - Type: **Custom TCP**
   - Port: **8000**
   - Source: **0.0.0.0/0** (anywhere)
4. **Save rules**

## Step 3: SSH into the Instance

On your Mac terminal:

```bash
# Make the key file readable only by you (required by SSH)
chmod 400 ~/Downloads/disaster-key.pem

# Connect (replace with your actual public IP)
ssh -i ~/Downloads/disaster-key.pem ubuntu@YOUR_PUBLIC_IP
```

If it asks "Are you sure you want to continue connecting?", type `yes` and hit Enter.

## Step 4: Run the Deployment Script

Once you're SSHed into the instance, run:

```bash
wget https://raw.githubusercontent.com/mmulic/Capstone-project/ahmad/deploy/ec2_deploy.sh
chmod +x ec2_deploy.sh
./ec2_deploy.sh
```

This installs Docker, clones the repo, builds the image, and starts everything. Takes about 5-10 minutes.

When it finishes, you'll see:

```
✅ Deployment complete!
📡 Backend API:    http://YOUR_PUBLIC_IP:8000
📖 Swagger docs:   http://YOUR_PUBLIC_IP:8000/docs
```

## Step 5: Verify It Works

Open in your browser:

**`http://YOUR_PUBLIC_IP:8000/docs`**

You should see the Swagger UI with all 18 endpoints. Try the health check endpoint to confirm the database is connected.

---

## Updating After Code Changes

Whenever you push new code to GitHub, redeploy with one command on the EC2 instance:

```bash
cd ~/Capstone-project && git pull && sudo docker compose up -d --build
```

## Adding the Gemini API Key

When the ML teammate provides their Gemini API key:

```bash
nano ~/Capstone-project/.env
```

Find the `GEMINI_API_KEY=` line, paste the key after the `=`, save with Ctrl+O / Enter / Ctrl+X.

Then restart:

```bash
cd ~/Capstone-project && sudo docker compose restart app
```

## Troubleshooting

**Container won't start:**
```bash
sudo docker compose logs app
```

**Out of disk space:**
```bash
sudo docker system prune -a
```

**Need to start over:**
```bash
cd ~/Capstone-project
sudo docker compose down -v  # -v removes the database volume
sudo docker compose up -d --build
```

**Forgot the public IP:**
```bash
curl http://169.254.169.254/latest/meta-data/public-ipv4
```

---

## Important Notes

- **The public IP changes** when you stop/start the instance. To keep a stable IP, allocate an **Elastic IP** in EC2 → Network & Security → Elastic IPs (~$3/month).
- **Data lives on the instance** — if it's terminated, the database is gone. Take EBS snapshots before any major changes.
- **No HTTPS yet** — for the demo, http:// is fine. To add HTTPS, set up Nginx + Let's Encrypt or put it behind a CloudFront distribution.
- **Stop the instance when not in use** to save money. Stopped instances don't bill for compute (only ~$3/month for storage).
