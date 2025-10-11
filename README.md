# Cynthia Health Institute — Hospital API & Mini Site

A compact, production-style demo of a hospital platform built with **Flask**, **SQLAlchemy**, **Gunicorn**, **Docker**, and **AWS S3** for images.

- Patients, Doctors, Appointments (SQLite)
- Photo uploads to **S3** (Pillow-optimized JPEG + presigned URLs)
- Public, modern homepage at **`/site`** (hero, services, founder, live directory)
- Simple **admin console** at **`/console`** (create records, upload photos)
- Token-based admin auth (HTTP Bearer)

> **Project by:** **Cynthia Udie** — *This project was created and built by Cynthia Udie.*

---

## Live

- **Public site:** https://api.cynthiaudieonline.online/site  
- **Health:** https://api.cynthiaudieonline.online/health  
- **Admin console:** https://api.cynthiaudieonline.online/console  
  - For browser testing only, you may use:  
    `https://api.cynthiaudieonline.online/console?token=<ADMIN_TOKEN>`  
    *(Use real HTTP headers in production.)*

---

## Architecture

- **Flask** app (`app.py`) with **SQLAlchemy** models (`models.py`) and DB session/engine in `db.py`.
- **SQLite** persisted at `/app/data/hospital.sqlite3` (mounted as a host volume in Docker).
- **AWS S3** stores photos; app returns **presigned GET URLs** to display images safely.
- **Gunicorn** serves the app; **Nginx** terminates TLS and proxies to the container.

---

## Environment

Create a `.env` (do **not** commit real secrets):


