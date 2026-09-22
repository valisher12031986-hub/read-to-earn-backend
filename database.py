from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///./read_to_earn.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    coins_balance = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    reading_sessions = relationship("ReadingSession", back_populates="user")

class ReadingSession(Base):
    __tablename__ = "reading_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    chapter_id = Column(Integer, nullable=False)
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    duration_seconds = Column(Integer, default=0)
    is_completed = Column(Boolean, default=False)

    user = relationship("User", back_populates="reading_sessions")

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
