# Cynthia Health Institute — Hospital API & Mini Site

A compact, production-style demo of a hospital platform built with **Flask**, **SQLAlchemy**, **Gunicorn**, **Docker**, and **AWS S3** for images.

- Patients, Doctors, Appointments (SQLite)
- Photo uploads to **S3** (Pillow-optimized JPEG + presigned URLs)
- Public, modern homepage at **/site** (hero, services, founder, live directory)
- Simple **admin console** at **/console** (create records, upload photos)
- Token-based admin auth (HTTP Bearer)

> **Project by:** **Cynthia Udie** — *This project was created and built by Cynthia Udie.*

---

## Live

- Public site: https://api.cynthiaudieonline.online/site  
- Health: https://api.cynthiaudieonline.online/health

> The site pulls live Doctors/Patients from the API and displays photos via S3 presigned URLs.

---

## API Overview

| Method | Path               | Auth          | Notes                                  |
|-------:|--------------------|---------------|----------------------------------------|
| GET    | `/health`          | none          | Liveness check.                         |
| GET    | `/patients`        | none          | List patients (includes `photo_url`).  |
| POST   | `/patients`        | Bearer token  | Create patient `{ full_name, phone }`. |
| POST   | `/patients/photo`  | Bearer token  | Multipart upload: `id`, `file`.        |
| GET    | `/doctors`         | none          | List doctors.                           |
| POST   | `/doctors`         | Bearer token  | Create doctor `{ full_name, specialty }`. |
| POST   | `/doctors/photo`   | Bearer token  | Multipart upload: `id`, `file`.        |
| GET    | `/appointments`    | none          | List appointments.                      |
| POST   | `/appointments`    | Bearer token  | Create appointment.                     |
| GET    | `/console`         | Bearer token  | Minimal admin UI for data/photo ops.    |
| GET    | `/site`            | none          | Polished homepage (project showcase).   |
| GET    | `/me`              | header/param  | Shows whether current request is admin. |

**Admin Auth**  
- Header: `Authorization: Bearer <ADMIN_TOKEN>`  
- Or query string (demo only): `?token=<ADMIN_TOKEN>` on routes like `/console` (use headers in production).

---

## Architecture

- **Flask** app with thin routes.
- **SQLAlchemy** models + **SQLite** (file persisted at `/app/data/hospital.sqlite3`).
- **Images** stored in **AWS S3**. Uploads are normalized to ~1024px JPEG via **Pillow**; served with **presigned URLs**.
- **Gunicorn** as WSGI server.  
- **Nginx (front)** terminates TLS and proxies to the container on `127.0.0.1:8000`.

---

## Local Development (Docker)

Create a `.env` (do **not** commit secrets publicly):
```ini
PORT=8000
AWS_REGION=eu-north-1
S3_BUCKET=hospital-photos-udiecynthia-eu-north-1
PHOTO_URL_TTL_SECONDS=604800
ADMIN_TOKEN=REDACTED
ADMIN_USER=admin@cynthiainstitute.com
ADMIN_PASSWORD=CHOOSE_A_STRONG_PASSWORD
DATABASE_URL=sqlite:////app/data/hospital.sqlite3
Build & run:

bash
Copy code
docker build -t udiecynthia/hospital-api:latest .
docker run -d --name hospital-api \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -p 127.0.0.1:8000:8000 \
  --restart unless-stopped \
  udiecynthia/hospital-api:latest \
  gunicorn --log-level info -w 1 -b 0.0.0.0:8000 app:app
Quick test:

bash
Copy code
curl -sS http://127.0.0.1:8000/health
Minimal Admin Console
Open (demo token via query string, or send the Bearer header in tools like curl/Postman):

arduino
Copy code
https://api.cynthiaudieonline.online/console?token=<ADMIN_TOKEN>
From there you can:

create doctors/patients,

upload doctor/patient photos,

and refresh the directory grid.

Notes on Images & README assets
Runtime images live in S3. For permanent README screenshots, put static copies under assets/ and reference them in Markdown:

Copy code
assets/
  founder.jpg
  homepage.png
(You can download your current S3 images and place copies in assets/ if you want the README to render images without depending on expiring presigned URLs.)

Teardown & Backup
Stop the container:

bash
Copy code
docker rm -f hospital-api
Your database persists on the host (because of -v .../data:/app/data).
Back it up:

bash
Copy code
cp ~/hospital-api-repo/data/hospital.sqlite3 ~/hospital.sqlite3.backup.$(date +%F)
License
MIT (for the demo code). Content and brand © 2025 Cynthia Udie.
