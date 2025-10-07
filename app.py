import os, io, uuid
from flask import Flask, jsonify, request, Response
from sqlalchemy.orm import Session
from PIL import Image
import boto3
from dotenv import load_dotenv

from db import Base, engine, SessionLocal
from models import Patient, Doctor, Appointment

load_dotenv()  # <-- loads .env into environment

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB uploads
Base.metadata.create_all(bind=engine)

AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")
S3_BUCKET = os.getenv("S3_BUCKET")
PHOTO_URL_TTL = int(os.getenv("PHOTO_URL_TTL_SECONDS", "604800"))
PORT = int(os.getenv("PORT", "8000"))

s3 = boto3.client("s3", region_name=AWS_REGION)
ALLOWED = {"png", "jpg", "jpeg", "webp"}

def presigned_get(key: str) -> str | None:
    if not key: return None
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=PHOTO_URL_TTL
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

@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200

# ---- Patients ----
@app.get("/patients")
def patients_list():
    with SessionLocal() as db:
        items = db.query(Patient).all()
        return jsonify([{
            "id": p.id, "full_name": p.full_name, "phone": p.phone,
            "photo_url": presigned_get(p.photo_key)
        } for p in items])

@app.post("/patients")
def patients_create():
    data = request.get_json(force=True)
    with SessionLocal() as db:
        p = Patient(full_name=data["full_name"], phone=data.get("phone"))
        db.add(p); db.commit(); db.refresh(p)
        return jsonify({"id": p.id, "full_name": p.full_name, "phone": p.phone}), 201

@app.post("/patients/photo")
def patients_photo():
    patient_id = request.form.get("id")
    file = request.files.get("file")
    if not patient_id or not file: return jsonify({"error":"id and file required"}), 400
    ext = file.filename.rsplit(".",1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED: return jsonify({"error":"allowed: jpg,jpeg,png,webp"}), 400
    with SessionLocal() as db:
        p = db.get(Patient, int(patient_id))
        if not p: return jsonify({"error":"Patient not found"}), 404
        key = save_photo_to_s3(file, "patients", p.id)
        p.photo_key = key; db.commit()
        return jsonify({"id": p.id, "photo_url": presigned_get(key)}), 201

# ---- Doctors ----
@app.get("/doctors")
def doctors_list():
    with SessionLocal() as db:
        items = db.query(Doctor).all()
        return jsonify([{
            "id": d.id, "full_name": d.full_name, "specialty": d.specialty,
            "photo_url": presigned_get(d.photo_key)
        } for d in items])

@app.post("/doctors")
def doctors_create():
    data = request.get_json(force=True)
    with SessionLocal() as db:
        d = Doctor(full_name=data["full_name"], specialty=data.get("specialty"))
        db.add(d); db.commit(); db.refresh(d)
        return jsonify({"id": d.id, "full_name": d.full_name, "specialty": d.specialty}), 201

@app.post("/doctors/photo")
def doctors_photo():
    doctor_id = request.form.get("id")
    file = request.files.get("file")
    if not doctor_id or not file: return jsonify({"error":"id and file required"}), 400
    ext = file.filename.rsplit(".",1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED: return jsonify({"error":"allowed: jpg,jpeg,png,webp"}), 400
    with SessionLocal() as db:
        d = db.get(Doctor, int(doctor_id))
        if not d: return jsonify({"error":"Doctor not found"}), 404
        key = save_photo_to_s3(file, "doctors", d.id)
        d.photo_key = key; db.commit()
        return jsonify({"id": d.id, "photo_url": presigned_get(key)}), 201

# ---- Appointments ----
@app.get("/appointments")
def appt_list():
    with SessionLocal() as db:
        appts = db.query(Appointment).all()
        return jsonify([{
            "id": a.id, "patient_id": a.patient_id, "doctor_id": a.doctor_id,
            "date_time": a.date_time.isoformat(), "reason": a.reason
        } for a in appts])

@app.post("/appointments")
def appt_create():
    data = request.get_json(force=True)
    with SessionLocal() as db:
        a = Appointment(patient_id=data["patient_id"], doctor_id=data.get("doctor_id"), reason=data.get("reason"))
        db.add(a); db.commit(); db.refresh(a)
        return jsonify({
            "id": a.id, "patient_id": a.patient_id, "doctor_id": a.doctor_id,
            "date_time": a.date_time.isoformat(), "reason": a.reason
        }), 201

# ---- Simple browser console ----
@app.get("/console")
def console():
    html = """
    <html><body style="font-family: system-ui; max-width: 900px; margin:2rem auto;">
      <h2>Hospital Console</h2>
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
              '<div style="margin-top:6px;font-weight:600">'+x.full_name+'</div>' +
              '<div style="color:#555">'+(x.specialty||x.phone||'')+'</div>' +
            '</div>').join('') + '</div>';
          document.getElementById('out').innerHTML = h(patients,'Patients') + h(doctors,'Doctors');
        }
      </script>
    </body></html>
    """
    return Response(html, mimetype="text/html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
