# Cynthia Health Institute — Hospital API & Mini Site

A compact, production-style demo of a hospital platform built with **Flask**, **SQLAlchemy**, **Gunicorn**, **Docker**, and **AWS S3** for images.

- Patients, Doctors, Appointments (SQLite)
- Photo uploads to **S3** (Pillow-optimized JPEG + presigned URLs)
- Public, modern homepage at **`/site`** (hero, services, founder, live directory)
- Simple **admin console** at **`/console`** (create records, upload photos)
- Token-based admin auth (HTTP **Bearer**)

> **Project by:** **Cynthia Udie** — *This project was created and built by Cynthia Udie.*

---

## Live

- Public site: https://api.cynthiaudieonline.online/site  
- Health: https://api.cynthiaudieonline.online/health  
- Admin console (demo shortcut): `https://api.cynthiaudieonline.online/console?token=<ADMIN_TOKEN>`  
  *(Use the **Authorization: Bearer \<token\>** header for real use.)*

---

## Quick Start (Docker)

```bash
# Clone
git clone https://github.com/Udie-Cynthia/hospital-api.git
cd hospital-api

# Configure
cp .env.example .env
# Required in .env:
#   ADMIN_TOKEN=your_strong_token
#   AWS_REGION=eu-north-1
#   S3_BUCKET=hospital-photos-udiecynthia-eu-north-1
#   DATABASE_URL=sqlite:////app/data/hospital.sqlite3
# Optional:
#   PHOTO_URL_TTL_SECONDS=604800
#   PORT=8000

# Run
docker run -d --name hospital-api \
  --env-file ./.env \
  -v "$(pwd)/data:/app/data" \
  -p 127.0.0.1:8000:8000 \
  --restart unless-stopped \
  udiecynthia/hospital-api:latest
