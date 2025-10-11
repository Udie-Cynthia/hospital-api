import os, io, uuid, json
from functools import wraps
from datetime import timedelta
from flask import Flask, jsonify, request, Response, redirect, make_response
from PIL import Image
import boto3
from dotenv import load_dotenv

from db import Base, engine, SessionLocal
from models import Patient, Doctor, Appointment

load_dotenv()

# ---------------- App & config ----------------
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB uploads
app.config["PREFERRED_URL_SCHEME"] = "https"
Base.metadata.create_all(bind=engine)

AWS_REGION   = os.getenv("AWS_REGION", "eu-north-1")
S3_BUCKET    = os.getenv("S3_BUCKET")
PHOTO_TTL    = int(os.getenv("PHOTO_URL_TTL_SECONDS", "604800"))  # 7d
PORT         = int(os.getenv("PORT", "8000"))

ADMIN_TOKEN  = os.getenv("ADMIN_TOKEN", "")
ADMIN_USER   = os.getenv("ADMIN_USER", "")
ADMIN_PASS   = os.getenv("ADMIN_PASSWORD", "")

HOSPITAL     = os.getenv("HOSPITAL_NAME", "Cynthia Health Institute")
FOUNDER      = os.getenv("FOUNDER_NAME", "Cynthia Udie")

s3 = boto3.client("s3", region_name=AWS_REGION)
ALLOWED = {"png", "jpg", "jpeg", "webp"}

# ---------------- Helpers ----------------
def presigned_get(key: str):
    if not key or not S3_BUCKET:
        return None
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=PHOTO_TTL
    )

def save_photo_to_s3(file_storage, prefix: str, entity_id: int) -> str:
    raw = file_storage.read()
    if not raw:
        raise ValueError("Empty file")
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    img.thumbnail((1024, 1024))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90, optimize=True)
    out.seek(0)
    key = f"{prefix}/{entity_id}/photo-{uuid.uuid4().hex}.jpg"
    s3.put_object(
        Bucket=S3_BUCKET, Key=key, Body=out,
        ContentType="image/jpeg", CacheControl="max-age=31536000, public"
    )
    return key

def _extract_token():
    # Header
    hdr = request.headers.get("Authorization", "")
    if hdr.startswith("Bearer "):
        return hdr[7:].strip()
    # Cookie
    c = request.cookies.get("Authorization", "")
    if c.startswith("Bearer "):
        return c[7:].strip()
    # Query param
    q = request.args.get("token", "")
    if q:
        return q.strip()
    return ""

def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        tok = _extract_token()
        if not ADMIN_TOKEN:
            return jsonify({"error":"admin token not configured"}), 500
        if tok != ADMIN_TOKEN:
            return jsonify({"error":"unauthorized"}), 401
        return f(*args, **kwargs)
    return wrapper

# ---------------- Health / Me ----------------
@app.get("/health")
def health():
    return jsonify({"status":"ok"})

@app.get("/me")
def me():
    tok = _extract_token()
    return jsonify({
        "is_admin": bool(ADMIN_TOKEN and tok == ADMIN_TOKEN),
        "user": ADMIN_USER if tok == ADMIN_TOKEN else None
    })

# ---------------- Patients ----------------
@app.get("/patients")
def patients_list():
    with SessionLocal() as db:
        items = db.query(Patient).all()
        return jsonify([{
            "id": p.id, "full_name": p.full_name, "phone": p.phone,
            "photo_url": presigned_get(p.photo_key)
        } for p in items])

@app.post("/patients")
@require_admin
def patients_create():
    data = request.get_json(force=True)
    with SessionLocal() as db:
        p = Patient(full_name=data["full_name"], phone=data.get("phone"))
        db.add(p); db.commit(); db.refresh(p)
        return jsonify({"id": p.id, "full_name": p.full_name, "phone": p.phone}), 201

@app.post("/patients/photo")
@require_admin
def patients_photo():
    pid = request.form.get("id")
    file = request.files.get("file")
    if not pid or not file:
        return jsonify({"error":"id and file required"}), 400
    ext = file.filename.rsplit(".",1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED:
        return jsonify({"error":"allowed: jpg,jpeg,png,webp"}), 400
    with SessionLocal() as db:
        p = db.get(Patient, int(pid))
        if not p: return jsonify({"error":"Patient not found"}), 404
        key = save_photo_to_s3(file, "patients", p.id)
        p.photo_key = key; db.commit()
        return jsonify({"id": p.id, "photo_url": presigned_get(key)}), 201

# ---------------- Doctors ----------------
@app.get("/doctors")
def doctors_list():
    with SessionLocal() as db:
        items = db.query(Doctor).all()
        return jsonify([{
            "id": d.id, "full_name": d.full_name, "specialty": d.specialty,
            "photo_url": presigned_get(d.photo_key)
        } for d in items])

@app.post("/doctors")
@require_admin
def doctors_create():
    data = request.get_json(force=True)
    with SessionLocal() as db:
        d = Doctor(full_name=data["full_name"], specialty=data.get("specialty"))
        db.add(d); db.commit(); db.refresh(d)
        return jsonify({"id": d.id, "full_name": d.full_name, "specialty": d.specialty}), 201

@app.post("/doctors/photo")
@require_admin
def doctors_photo():
    did = request.form.get("id")
    file = request.files.get("file")
    if not did or not file:
        return jsonify({"error":"id and file required"}), 400
    ext = file.filename.rsplit(".",1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED:
        return jsonify({"error":"allowed: jpg,jpeg,png,webp"}), 400
    with SessionLocal() as db:
        d = db.get(Doctor, int(did))
        if not d: return jsonify({"error":"Doctor not found"}), 404
        key = save_photo_to_s3(file, "doctors", d.id)
        d.photo_key = key; db.commit()
        return jsonify({"id": d.id, "photo_url": presigned_get(key)}), 201

# ---------------- Appointments ----------------
@app.get("/appointments")
def appt_list():
    with SessionLocal() as db:
        appts = db.query(Appointment).all()
        return jsonify([{
            "id": a.id, "patient_id": a.patient_id, "doctor_id": a.doctor_id,
            "date_time": a.date_time.isoformat() if getattr(a, "date_time", None) else None,
            "reason": a.reason
        } for a in appts])

@app.post("/appointments")
@require_admin
def appt_create():
    data = request.get_json(force=True)
    with SessionLocal() as db:
        a = Appointment(patient_id=data["patient_id"], doctor_id=data.get("doctor_id"), reason=data.get("reason"))
        db.add(a); db.commit(); db.refresh(a)
        return jsonify({
            "id": a.id, "patient_id": a.patient_id, "doctor_id": a.doctor_id,
            "date_time": a.date_time.isoformat() if getattr(a, "date_time", None) else None,
            "reason": a.reason
        }), 201

# ---------------- Auth pages ----------------
LOGIN_HTML = """
<!doctype html><html><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>%%HOSPITAL%% – Staff Login</title>
<style>
:root { --bg:#0b1022; --fg:#e5e7eb; --muted:#94a3b8; --card:#111633; --accent:#22d3ee; --line:#1f294a; }
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--fg);font-family:system-ui,-apple-system,Segoe UI,Roboto,Inter,sans-serif}
.wrap{max-width:420px;margin:8vh auto;padding:24px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}
.pad{padding:18px}
h1{margin:0 0 8px;font-size:22px}
.muted{color:var(--muted)}
.input{width:100%;padding:10px 12px;border-radius:10px;border:1px solid var(--line);background:#0c1430;color:var(--fg);margin:6px 0 10px}
.btn{width:100%;padding:12px;border-radius:10px;background:var(--accent);color:#031519;font-weight:800;border:0;cursor:pointer}
a{color:var(--accent);text-decoration:none}
.err{color:#ff8080;margin-top:8px;display:none}
</style></head><body>
  <div class="wrap">
    <div class="card"><div class="pad">
      <h1>%%HOSPITAL%%</h1>
      <div class="muted">Authorized access for staff and administrators.</div>
      <form id="f" onsubmit="login(event)">
        <input class="input" id="email" type="email" placeholder="Email" required/>
        <input class="input" id="pw" type="password" placeholder="Password" required/>
        <button class="btn">Sign In</button>
        <div id="err" class="err">Invalid credentials</div>
      </form>
      <div style="margin-top:10px"><a href="/site">Back to site</a></div>
    </div></div>
  </div>
<script>
async function login(e){
  e.preventDefault();
  const r = await fetch('/login', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ email: document.getElementById('email').value.trim(),
                           password: document.getElementById('pw').value })
  });
  if(r.ok){ location.href='/console'; }
  else{ document.getElementById('err').style.display='block'; }
}
</script></body></html>
"""

@app.get("/login")
def login_page():
    return Response(LOGIN_HTML.replace("%%HOSPITAL%%", HOSPITAL), mimetype="text/html")

@app.post("/login")
def login_post():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    pw    = data.get("password") or ""
    if ADMIN_USER and ADMIN_PASS and email.lower() == ADMIN_USER.lower() and pw == ADMIN_PASS:
        resp = make_response(jsonify({"ok":True}))
        # HttpOnly cookie with Bearer token (works through nginx/https)
        resp.set_cookie(
            "Authorization", f"Bearer {ADMIN_TOKEN}",
            max_age=int(timedelta(days=7).total_seconds()),
            path="/", secure=True, httponly=True, samesite="Lax"
        )
        return resp
    return jsonify({"error":"invalid"}), 401

@app.get("/logout")
def logout():
    resp = make_response(redirect("/site", code=302))
    resp.set_cookie("Authorization", "", max_age=0, path="/", secure=True, httponly=True, samesite="Lax")
    return resp

@app.get("/login/token")
def login_token():
    # Quick login via URL: /login/token?token=...
    tok = request.args.get("token","")
    if tok and ADMIN_TOKEN and tok == ADMIN_TOKEN:
        resp = make_response(redirect("/console", code=302))
        resp.set_cookie(
            "Authorization", f"Bearer {ADMIN_TOKEN}",
            max_age=int(timedelta(days=7).total_seconds()),
            path="/", secure=True, httponly=True, samesite="Lax"
        )
        return resp
    return jsonify({"error":"unauthorized"}), 401

# ---------------- Admin Console (cookie or header auth) ----------------
@app.get("/console")
@require_admin
def console():
    html = """
    <html><body style="font-family: system-ui; max-width: 900px; margin:2rem auto;">
      <h2>Hospital Console</h2>
      <p><a href="/logout">Log out</a></p>

      <h3>Create Patient</h3>
      <form onsubmit="createPatient(event)">
        <input placeholder="Full name" id="pname"/> <input placeholder="Phone" id="pphone"/>
        <button>Create</button>
      </form>

      <h3>Upload Patient Photo</h3>
      <form id="pf" method="post" enctype="multipart/form-data" action="/patients/photo">
        <input name="id" placeholder="Patient ID" required />
        <input type="file" name="file" accept=".jpg,.jpeg,.png,.webp" required />
        <button>Upload</button>
      </form>

      <h3>Create Doctor</h3>
      <form onsubmit="createDoctor(event)">
        <input placeholder="Full name" id="dname"/> <input placeholder="Specialty" id="dspec"/>
        <button>Create</button>
      </form>

      <h3>Upload Doctor Photo</h3>
      <form id="df" method="post" enctype="multipart/form-data" action="/doctors/photo">
        <input name="id" placeholder="Doctor ID" required />
        <input type="file" name="file" accept=".jpg,.jpeg,.png,.webp" required />
        <button>Upload</button>
      </form>

      <h3>Current People</h3>
      <button onclick="loadAll()">Refresh</button>
      <div id="out"></div>

      <script>
        async function createPatient(e){e.preventDefault();
          const r = await fetch('/patients',{method:'POST',headers:{'Content-Type':'application/json'},
            body: JSON.stringify({full_name: document.getElementById('pname').value, phone: document.getElementById('pphone').value})});
          alert(await r.text());
        }
        async function createDoctor(e){e.preventDefault();
          const r = await fetch('/doctors',{method:'POST',headers:{'Content-Type':'application/json'},
            body: JSON.stringify({full_name: document.getElementById('dname').value, specialty: document.getElementById('dspec').value})});
          alert(await r.text());
        }
        async function loadAll(){
          const [p,d] = await Promise.all([fetch('/patients'), fetch('/doctors')]);
          const patients = await p.json(), doctors = await d.json();
          const h = (list,title)=> '<h4>'+title+'</h4><div style="display:grid;grid-template-columns:repeat(auto-fill, minmax(180px,1fr));gap:10px;">' +
            list.map(x=>'<div style="border:1px solid #ddd;border-radius:12px;padding:10px">'+
              (x.photo_url?'<img src="'+x.photo_url+'" style="width:100%;height:160px;object-fit:cover;border-radius:8px;"/>' : '<div style="height:160px;background:#f4f4f4;border-radius:8px;display:grid;place-items:center;color:#888">No photo</div>')+
              '<div style="margin-top:6px;font-weight:600">'+(x.full_name||'')+'</div>' +
              '<div style="color:#555">'+(x.specialty||x.phone||'')+'</div>' +
            '</div>').join('') + '</div>';
          document.getElementById('out').innerHTML = h(patients,'Patients') + h(doctors,'Doctors');
        }
        loadAll();
      </script>
    </body></html>
    """
    return Response(html, mimetype="text/html")

# ---------------- Public Homepage ----------------
SITE_HTML = """
<!doctype html><html><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>%%HOSPITAL%%</title>
<style>
:root { --bg:#0b1022; --fg:#e5e7eb; --muted:#94a3b8; --card:#111633; --accent:#22d3ee; --line:#1f294a; }
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--fg);font-family:system-ui,-apple-system,Segoe UI,Roboto,Inter,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:24px}
.header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
.brand{font-size:22px;font-weight:800;letter-spacing:0.2px}
.nav a{color:var(--fg);opacity:.9;text-decoration:none;margin-left:16px}
.hero{display:grid;grid-template-columns:1.2fr .8fr;gap:22px;align-items:center;padding:24px 0;border-bottom:1px solid var(--line)}
.tag{font-size:38px;font-weight:900;line-height:1.1;margin:0 0 10px}
.sub{color:var(--muted);margin-top:8px}
.cta{display:inline-block;margin-top:14px;background:var(--accent);color:#031519;font-weight:800;border-radius:10px;padding:10px 16px;text-decoration:none}
.section-title{font-weight:900;margin:26px 0 12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill, minmax(220px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden}
.img{width:100%;height:150px;object-fit:cover;background:#0c1430}
.pad{padding:14px}
.name{font-weight:800}
.muted{color:var(--muted)}
.founder{display:grid;grid-template-columns:.8fr 1.2fr;gap:18px;align-items:center;border:1px solid var(--line);background:var(--card);border-radius:16px;overflow:hidden}
.founder .ph{height:240px;background:#0c1430;display:grid;place-items:center;color:var(--muted)}
.contact a{color:var(--accent);text-decoration:none}
</style></head>
<body><div class="wrap">
  <div class="header">
    <div class="brand">%%HOSPITAL%%</div>
    <div class="nav">
      <a href="/site">About</a>
      <a href="/site#services">Services</a>
      <a href="/site#directory">Directory</a>
      <a href="/site#testimonials">Testimonials</a>
      <a href="/login">Login</a>
    </div>
  </div>

  <section class="hero">
    <div>
      <div class="tag">World-class care, delivered with heart.</div>
      <div class="sub">%%HOSPITAL%% blends compassionate clinicians with evidence-based medicine, modern diagnostics, and a seamless patient experience.</div>
      <div class="sub"><b>This project was created and built by %%FOUNDER%%.</b></div>
      <a class="cta" href="#services">Explore Our Services</a>
    </div>
    <div class="founder">
      <div id="founder-photo-box" class="ph">Founder photo will appear here</div>
      <div class="pad">
        <div class="section-title">Meet %%FOUNDER%%, Founder of %%HOSPITAL%%</div>
        <div class="muted">%%FOUNDER%% created and built this project to demonstrate how modern hospitals can pair clinical excellence with intuitive digital experiences. Vision: safe, respectful, and timely care — supported by clear communication, smart technology, and continuous improvement.</div>
      </div>
    </div>
  </section>

  <section id="services">
    <div class="section-title">Services</div>
    <div class="grid">
      <div class="card"><div class="pad"><div class="name">Primary & Family Medicine</div><div class="muted">Preventive care, annual checkups, and chronic condition management for all ages.</div></div></div>
      <div class="card"><div class="pad"><div class="name">Cardiology</div><div class="muted">Heart health assessments, ECG/Echo diagnostics, and personalized treatment plans.</div></div></div>
      <div class="card"><div class="pad"><div class="name">Obstetrics & Gynecology</div><div class="muted">Women’s health, prenatal care, and family planning in a supportive setting.</div></div></div>
      <div class="card"><div class="pad"><div class="name">Pediatrics</div><div class="muted">Well-child visits, immunizations, and same-day sick care with a family-first approach.</div></div></div>
      <div class="card"><div class="pad"><div class="name">Diagnostics & Imaging</div><div class="muted">On-site lab services and imaging for faster, more accurate results.</div></div></div>
      <div class="card"><div class="pad"><div class="name">Telehealth & e-Consults</div><div class="muted">Secure virtual visits for follow-ups and routine consultations.</div></div></div>
    </div>
  </section>

  <section id="directory">
    <div class="section-title">Team & Patients</div>
    <div class="section-title" style="margin-top:10px;">Doctors</div>
    <div class="grid" id="doctors"></div>
    <div class="section-title" style="margin-top:22px;">Patients</div>
    <div class="grid" id="patients"></div>
  </section>

  <section id="testimonials">
    <div class="section-title">Testimonials (Demo/Mock)</div>
    <div class="grid">
      <div class="card"><div class="pad"><div class="name">Fortune</div><div class="muted">“From booking to follow-up, everything felt coordinated and caring. I felt heard.” (demo)</div></div></div>
      <div class="card"><div class="pad"><div class="name">Ose</div><div class="muted">“The doctors explained my options clearly and the staff were incredibly professional.” (demo)</div></div></div>
      <div class="card"><div class="pad"><div class="name">Tabi</div><div class="muted">“Fast diagnostics, clear results, and compassionate care—highly recommended.” (demo)</div></div></div>
    </div>
  </section>

  <footer id="contact" style="margin-top:26px">
    <div class="section-title">Contact</div>
    <div class="muted">
      <div>Phone: <a href="tel:+2348154986548">+234 815 498 6548</a></div>
      <div>Email: <a href="mailto:udiecynthia@gmail.com">udiecynthia@gmail.com</a></div>
      <div>LinkedIn: <a target="_blank" rel="noopener" href="https://www.linkedin.com/in/cynthia-udie-68936135b?utm_source=share&utm_campaign=share_via&utm_content=profile&utm_medium=ios_app">linkedin.com/in/cynthia-udie-68936135b</a></div>
      <div style="margin-top:8px;">© 2025 %%HOSPITAL%%. All rights reserved.</div>
    </div>
  </footer>
</div>

<script>
function renderCards(list){
  return list.map(x=>`
    <div class="card">
      ${x.photo_url ? `<img class="img" src="${x.photo_url}" alt="">` : `<div class="img"></div>`}
      <div class="pad">
        <div class="name">${x.full_name||''}</div>
        <div class="muted">${x.specialty || x.phone || ''}</div>
      </div>
    </div>`).join('');
}
function pickFounderPhoto(doctors){
  const founderName = %%FOUNDER_JS%%;
  let match = doctors.find(d => (d.full_name||'').toLowerCase().includes('cynthia') || (d.full_name||'').toLowerCase().includes('udie'))
             || doctors.find(d => d.photo_url) || null;
  if(match && match.photo_url){
    const box = document.getElementById('founder-photo-box');
    box.innerHTML = `<img class="img" style="height:240px;object-fit:cover" src="${match.photo_url}" alt="Photo of ${founderName}" />`;
  }
}
async function loadDirectory(){
  const [dr, pt] = await Promise.all([fetch('/doctors').then(r=>r.json()), fetch('/patients').then(r=>r.json())]);
  document.getElementById('doctors').innerHTML = renderCards(dr);
  document.getElementById('patients').innerHTML = renderCards(pt);
  pickFounderPhoto(dr);
}
loadDirectory();
</script>
</body></html>
"""

@app.get("/site")
def site():
    html = SITE_HTML.replace("%%HOSPITAL%%", HOSPITAL)\
                    .replace("%%FOUNDER%%", FOUNDER)\
                    .replace("%%FOUNDER_JS%%", json.dumps(FOUNDER))
    return Response(html, mimetype="text/html")

@app.get("/")
def root():
    return redirect("/site", code=302)
