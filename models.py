from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from db import Base

class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(200), nullable=False)
    phone = Column(String(50))
    photo_key = Column(String(300))

class Doctor(Base):
    __tablename__ = "doctors"
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(200), nullable=False)
    specialty = Column(String(200))
    photo_key = Column(String(300))

class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"))
    date_time = Column(DateTime, server_default=func.now())
    reason = Column(String(500))

    patient = relationship("Patient")
    doctor = relationship("Doctor")
