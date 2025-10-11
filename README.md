cd ~/hospital-api-repo

cat > README.md <<'MARKDOWN'
# Cynthia Health Institute — Hospital API & Mini Site

A compact, production-style hospital demo built with **Flask**, **SQLAlchemy**, **Gunicorn**, **Docker**, and **AWS S3** (for images).

- Patients, Doctors, Appointments (SQLite)
- Photo uploads to **S3** (Pillow-optimized JPEG + **presigned URLs**)
- Public, modern homepage at **`/site`** (hero, services, **“Meet the Founder – Cynthia Udie”**, live directory)
- Simple **admin console** at **`/console`** (create records, upload photos)
- Token-based admin auth (HTTP **Bearer** header or **?token=...** for the console page)

> **Project by: _Cynthia Udie_** — **“This project was created and built by Cynthia Udie.”**

---

## Live

- Public site: https://api.cynthiaudieonline.online/site  
- Health: https://api.cynthiaudieonline.online/health  
- Admin console (demo-friendly): `https://api.cynthiaudieonline.online/console?token=<ADMIN_TOKEN>`  
  - In production, prefer the **Authorization** header: `Authorization: Bearer <ADMIN_TOKEN>`

---

## Quick Start (Docker)

```bash
# .env (example)
PORT=8000
AWS_REGION=eu-north-1
S3_BUCKET=hospital-photos-udiecynthia-eu-north-1
PHOTO_URL_TTL_SECONDS=604800
ADMIN_TOKEN=REDACTED
ADMIN_USER=admin@cynthiainstitute.com
ADMIN_PASSWORD=REDACTED
DATABASE_URL=sqlite:////app/data/hospital.sqlite3
