from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import datetime

# --- MA'LUMOTLAR BAZASI SOZLAMALARI ---
DATABASE_URL = "sqlite:///./database.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- MODEL (BAZA JADVALI) ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)  # Telefon raqami saqlanadigan ustun
    coins_balance = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ReadingSession(Base):
    __tablename__ = "reading_sessions"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, nullable=False)
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    last_heartbeat = Column(DateTime, default=datetime.datetime.utcnow)
    is_completed = Column(Integer, default=0)

Base.metadata.create_all(bind=engine)

# --- FASTAPI TIZIMI ---
app = FastAPI(title="Read-to-Earn Backend")

# CORS sozlamasi (Frontend va Backend erkin bog'lanishi uchun)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB Sessiyasini olish
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- PYDANTIC MODELLARI (REQUEST BODY) ---
class UserAuth(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    phone_number: Optional[str] = None

class SessionStart(BaseModel):
    telegram_id: int

class Heartbeat(BaseModel):
    telegram_id: int
    session_id: int

class QuizClaim(BaseModel):
    telegram_id: int
    session_id: int
    selected_answer: int

# --- ROOT ENDPOINT (Render orqali ham sahifa ko'rinishi uchun) ---
@app.get("/", response_class=HTMLResponse)
def read_root():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "<h1>Read-to-Earn Backend API ishlayapti!</h1>"

# --- AUTH ENDPOINT (TELEFON RAQAM VA USER SAQLASH) ---
@app.post("/api/auth")
def auth_user(data: UserAuth, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == data.telegram_id).first()
    
    if not user:
        user = User(
            telegram_id=data.telegram_id,
            username=data.username,
            phone_number=data.phone_number,
            coins_balance=0
        )
        db.add(user)
    else:
        # Yangi ma'lumot kelgan bo'lsa yangilaymiz
        if data.phone_number:
            user.phone_number = data.phone_number
        if data.username:
            user.username = data.username

    db.commit()
    db.refresh(user)
    
    return {
        "status": "ok",
        "user_id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "phone_number": user.phone_number,
        "coins_balance": user.coins_balance
    }

# --- O'QISH SESSIYASINI BOSHLASH ---
@app.post("/api/start-session")
def start_session(data: SessionStart, db: Session = Depends(get_db)):
    session = ReadingSession(telegram_id=data.telegram_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"status": "ok", "session_id": session.id}

# --- HEARTBEAT (HAR 30 SONIYADA FAOLIKNI TEKSHIRISH) ---
@app.post("/api/heartbeat")
def heartbeat(data: Heartbeat, db: Session = Depends(get_db)):
    session = db.query(ReadingSession).filter(
        ReadingSession.id == data.session_id,
        ReadingSession.telegram_id == data.telegram_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Sessiya topilmadi")
    
    session.last_heartbeat = datetime.datetime.utcnow()
    db.commit()
    return {"status": "ok"}

# --- TEST YECHISH VA KOIN QO'SHISH ---
@app.post("/api/claim-quiz")
def claim_quiz(data: QuizClaim, db: Session = Depends(get_db)):
    session = db.query(ReadingSession).filter(
        ReadingSession.id == data.session_id,
        ReadingSession.telegram_id == data.telegram_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Sessiya topilmadi")
    
    if session.is_completed == 1:
        raise HTTPException(status_code=400, detail="Bu sessiya uchun allaqachon mukofot olingan")

    # To'g'ri javob indeksi 1 deb olsak (masalan 2-variant)
    if data.selected_answer != 1:
        return {"status": "wrong_answer", "message": "Noto'g'ri javob, qaytadan urinib ko'ring"}

    # Foydalanuvchi balansiga 10 koin qo'shish
    user = db.query(User).filter(User.telegram_id == data.telegram_id).first()
    if user:
        user.coins_balance += 10
        session.is_completed = 1
        db.commit()
        db.refresh(user)
        return {
            "status": "success",
            "coins_earned": 10,
            "new_balance": user.coins_balance
        }
    
    raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
