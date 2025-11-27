from pydantic import BaseModel
from typing import List, Optional

# То, что присылает пользователь
class QuestionRequest(BaseModel):
    text: str

# То, что мы отвечаем
class AnswerResponse(BaseModel):
    answer: str
    sources: List[str] = []
    cached: bool = False