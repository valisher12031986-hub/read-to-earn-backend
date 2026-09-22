from pydantic import BaseModel
from typing import Optional

class UserAuth(BaseModel):
    telegram_id: int
    username: Optional[str] = None

class StartReadingRequest(BaseModel):
    telegram_id: int
    chapter_id: int

class HeartbeatRequest(BaseModel):
    session_id: int
    telegram_id: int
    seconds_read: int

class SubmitQuizRequest(BaseModel):
    telegram_id: int
    session_id: int
    chapter_id: int
    correct_answers: int
    total_questions: int
