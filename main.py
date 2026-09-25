from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
import datetime

# --- MA'LUMOTLAR BAZASI SOZLAMALARI ---
DATABASE_URL = "sqlite:///./database.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- MODELLAR (BAZA JADVALLARI) ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    coins_balance = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    author = Column(String, nullable=False)
    cover_url = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    chapters = relationship("Chapter", back_populates="book")

class Chapter(Base):
    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    chapter_number = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    question = Column(String, nullable=False)
    option_a = Column(String, nullable=False)
    option_b = Column(String, nullable=False)
    option_c = Column(String, nullable=False)
    correct_option = Column(Integer, nullable=False) # 0, 1, 2
    
    book = relationship("Book", back_populates="chapters")

class ReadingSession(Base):
    __tablename__ = "reading_sessions"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, nullable=False)
    chapter_id = Column(Integer, nullable=True)
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    last_heartbeat = Column(DateTime, default=datetime.datetime.utcnow)
    is_completed = Column(Integer, default=0)

Base.metadata.create_all(bind=engine)

# --- FASTAPI TIZIMI ---
app = FastAPI(title="Read-to-Earn Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- PYDANTIC MODELLARI ---
class UserAuth(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    phone_number: Optional[str] = None

class SessionStart(BaseModel):
    telegram_id: int
    chapter_id: int

class Heartbeat(BaseModel):
    telegram_id: int
    session_id: int

class QuizClaim(BaseModel):
    telegram_id: int
    session_id: int
    selected_answer: int

# --- NAMUNA KITOB QO'SHISH (BAZA BO'SH BO'LSA) ---
def seed_initial_data(db: Session):
    if db.query(Book).count() == 0:
        book = Book(
            title="Turkiy guliston yohud axloq",
            author="Abdulla Avloniy",
            description="O'zbek xalqining ma'naviy va axloqiy tarbiyasida muhim o'rin tutuvchi asar."
        )
        db.add(book)
        db.commit()
        db.refresh(book)

        ch1 = Chapter(
            book_id=book.id,
            chapter_number=1,
            title="1-Bob: Intizom va Ilm",
            content="O'zbek xalqining ma'naviy va axloqiy tarbiyasida ushbu asar muhim o'rin tutadi. Intizom, ilm, tarbiya va odob har bir inson uchun eng zarur bo'lgan fazilatlardandir. Inson ma'rifatli bo'lishi uchun yoshligidan kitob o'qish va foydali ilmlarni o'rganishga intilishi lozim...",
            question="Inson ma'rifatli bo'lishi uchun nimaga intilishi lozim?",
            option_a="Faqat dam olishga",
            option_b="Kitob o'qish va ilmlarni o'rganishga",
            option_c="Kino ko'rishga",
            correct_option=1
        )
        ch2 = Chapter(
            book_id=book.id,
            chapter_number=2,
            title="2-Bob: Saxovat va Saxiylik",
            content="Saxovat — inson qalbinining go'zalligi va komilligi belgisidir. Saxovatli inson o'zgalarga yordam berishdan quvonch topadi va jamiyatda hurmat-e'tibor qozonadi...",
            question="Saxovat insonning qanday belgisi hisoblanadi?",
            option_a="Boylik ko'rsatgichi",
            option_b="Qalb go'zalligi va komillik belgisi",
            option_c="Kechikish sababi",
            correct_option=1
        )
        db.add_all([ch1, ch2])
        db.commit()

# --- ENDPOINT'LAR ---

@app.get("/", response_class=HTMLResponse)
def read_root():
    return "<h1>Read-to-Earn Backend API ishlayapti!</h1>"

@app.post("/api/auth")
def auth_user(data: UserAuth, db: Session = Depends(get_db)):
    seed_initial_data(db) # Baza bo'sh bo'lsa kitoblarni yuklaydi
    
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

# --- KITOBLAR RO'YXATINI OLISH ---
@app.get("/api/books")
def get_books(db: Session = Depends(get_db)):
    books = db.query(Book).all()
    result = []
    for b in books:
        result.append({
            "id": b.id,
            "title": b.title,
            "author": b.author,
            "description": b.description,
            "chapters_count": len(b.chapters)
        })
    return result

# --- KITOBNING BOBLARINI OLISH ---
@app.get("/api/books/{book_id}/chapters")
def get_chapters(book_id: int, db: Session = Depends(get_db)):
    chapters = db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.chapter_number).all()
    result = []
    for ch in chapters:
        result.append({
            "id": ch.id,
            "chapter_number": ch.chapter_number,
            "title": ch.title
        })
    return result

# --- AYNAN BITTA BOB MATNINI OLISH ---
@app.get("/api/chapters/{chapter_id}")
def get_chapter_detail(chapter_id: int, db: Session = Depends(get_db)):
    ch = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not ch:
        raise HTTPException(status_code=404, detail="Bob topilmadi")
    return {
        "id": ch.id,
        "title": ch.title,
        "content": ch.content,
        "question": ch.question,
        "options": [ch.option_a, ch.option_b, ch.option_c]
    }

# --- SESSIYA BOSHLASH (BOB BO'YICHA) ---
@app.post("/api/start-session")
def start_session(data: SessionStart, db: Session = Depends(get_db)):
    session = ReadingSession(telegram_id=data.telegram_id, chapter_id=data.chapter_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"status": "ok", "session_id": session.id}

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

@app.post("/api/claim-quiz")
def claim_quiz(data: QuizClaim, db: Session = Depends(get_db)):
    session = db.query(ReadingSession).filter(
        ReadingSession.id == data.session_id,
        ReadingSession.telegram_id == data.telegram_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Sessiya topilmadi")
    
    if session.is_completed == 1:
        raise HTTPException(status_code=400, detail="Mukofot allaqachon olingan")

    chapter = db.query(Chapter).filter(Chapter.id == session.chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Bob topilmadi")

    if data.selected_answer != chapter.correct_option:
        return {"status": "wrong_answer", "message": "Noto'g'ri javob, qaytadan urinib ko'ring!"}

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
