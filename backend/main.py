from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from uuid import uuid4
from datetime import datetime
import redis
import os
from sqlalchemy import create_engine, Column, String, Date, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import time
from sqlalchemy.exc import OperationalError

# Environment vars
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@db:5432/onkoflow")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

# FastAPI app
app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_RETRIES = 10
for i in range(MAX_RETRIES):
    try:
        engine = create_engine(DATABASE_URL)
        engine.connect()  # test connection
        break
    except OperationalError:
        print(f"[DB INIT] Attempt {i+1} failed, retrying in 3s...")
        time.sleep(3)
else:
    raise RuntimeError("Could not connect to the database after several attempts.")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Redis setup
r = redis.Redis.from_url(REDIS_URL)

# Models
class Snapshot(Base):
    __tablename__ = "snapshots"
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    birth_date = Column(Date)
    diagnosis = Column(Text)
    treatment = Column(Text)
    allergies = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# Request schema
class SnapshotCreate(BaseModel):
    name: str
    birth_date: str
    diagnosis: str
    treatment: str
    allergies: str
    notes: str | None = None

# Routes
@app.post("/snapshots")
def create_snapshot(data: SnapshotCreate):
    db = SessionLocal()
    snapshot_id = str(uuid4())
    snapshot = Snapshot(
        id=snapshot_id,
        name=data.name,
        birth_date=data.birth_date,
        diagnosis=data.diagnosis,
        treatment=data.treatment,
        allergies=data.allergies,
        notes=data.notes,
    )
    db.add(snapshot)
    db.commit()
    db.close()

    token = str(uuid4())
    r.setex(token, 3600, snapshot_id)  # expires in 1 hour
    return {"access_url": f"/snapshots/{token}"}

@app.get("/snapshots/{token}")
def get_snapshot(token: str):
    snapshot_id = r.get(token)
    if not snapshot_id:
        raise HTTPException(status_code=404, detail="Invalid or expired token")
    db = SessionLocal()
    snapshot = db.query(Snapshot).filter(Snapshot.id == snapshot_id.decode()).first()
    db.close()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return {
        "name": snapshot.name,
        "birth_date": str(snapshot.birth_date),
        "diagnosis": snapshot.diagnosis,
        "treatment": snapshot.treatment,
        "allergies": snapshot.allergies,
        "notes": snapshot.notes,
    }
