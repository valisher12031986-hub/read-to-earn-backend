from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import datetime

from database import get_db, User, ReadingSession
import schemas

app = FastAPI(title="Read-to-Earn Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MINIMUM_READING_SECONDS = 120
REWARD_PER_QUIZ = 10

@app.post("/api/auth")
def authenticate_user(user_data: schemas.UserAuth, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == user_data.telegram_id).first()
    if not user:
        user = User(telegram_id=user_data.telegram_id, username=user_data.username)
        db.add(user)
        db.commit()
        db.refresh(user)
    return {"status": "success", "user_id": user.id, "coins_balance": user.coins_balance}

@app.post("/api/reading/start")
def start_reading(data: schemas.StartReadingRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == data.telegram_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")

    new_session = ReadingSession(
        user_id=user.id,
        chapter_id=data.chapter_id,
        start_time=datetime.datetime.utcnow(),
        duration_seconds=0
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    return {"status": "started", "session_id": new_session.id}

@app.post("/api/reading/heartbeat")
def reading_heartbeat(data: schemas.HeartbeatRequest, db: Session = Depends(get_db)):
    session = db.query(ReadingSession).filter(ReadingSession.id == data.session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessiya topilmadi")

    if data.seconds_read > 35:
        raise HTTPException(status_code=400, detail="G'irromlik aniqlandi")

    session.duration_seconds += data.seconds_read
    db.commit()

    return {"status": "updated", "current_duration": session.duration_seconds}

@app.post("/api/reading/submit-quiz")
def submit_quiz(data: schemas.SubmitQuizRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.telegram_id == data.telegram_id).first()
    session = db.query(ReadingSession).filter(ReadingSession.id == data.session_id).first()

    if not user or not session:
        raise HTTPException(status_code=404, detail="Ma'lumot topilmadi")

    if session.is_completed:
        raise HTTPException(status_code=400, detail="Bu bob uchun mukofot allaqachon olingan")

    if session.duration_seconds < MINIMUM_READING_SECONDS:
        raise HTTPException(
            status_code=400, 
            detail=f"Kamida {MINIMUM_READING_SECONDS} soniya o'qishingiz kerak."
        )

    passing_score = data.total_questions * 0.66
    if data.correct_answers < passing_score:
        return {"status": "failed", "message": "Testdan o'ta olmadingiz.", "coins_earned": 0}

    user.coins_balance += REWARD_PER_QUIZ
    session.is_completed = True
    db.commit()

    return {
        "status": "success",
        "message": f"Tabriklaymiz! Sizga {REWARD_PER_QUIZ} koin berildi.",
        "new_balance": user.coins_balance
    }
