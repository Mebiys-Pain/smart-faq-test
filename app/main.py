import redis
from fastapi import FastAPI, Depends
from fastapi.staticfiles import StaticFiles  # <--- Нужно для статики
from fastapi.responses import FileResponse   # <--- Нужно для HTML
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

from app.database import engine, Base, get_db
from app import models, schemas, rag
from app.config import settings

# Подключение к Redis
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Старт
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="Smart FAQ Service", lifespan=lifespan)

# === НОВЫЙ БЛОК: ПОДКЛЮЧЕНИЕ САЙТА ===
# 1. Подключаем папку static, чтобы браузер видел файлы
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 2. Отдаем index.html при заходе на главную страницу
@app.get("/")
async def read_index():
    return FileResponse("app/static/index.html")
# ======================================

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "Smart FAQ"}

@app.post("/api/documents")
async def upload_documents():
    """Заставляет систему прочитать PDF из папки documents"""
    result = await rag.ingest_docs()
    return result

@app.post("/api/ask", response_model=schemas.AnswerResponse)
async def ask_question(req: schemas.QuestionRequest, db: AsyncSession = Depends(get_db)):
    question_text = req.text.strip()
    
    # 1. КЭШ
    cache_key = f"faq:{question_text.lower()}"
    cached_answer = redis_client.get(cache_key)
    
    if cached_answer:
        return schemas.AnswerResponse(answer=cached_answer, sources=["Redis Cache"], cached=True)

    # 2. RAG (Поиск + Генерация)
    answer_text, sources = await rag.ask_llm(question_text)
    
    # 3. База Данных
    tokens_est = int(len(answer_text.split()) * 1.3)
    db_record = models.RequestHistory(
        question=question_text,
        answer=answer_text,
        tokens_used=tokens_est
    )
    db.add(db_record)
    await db.commit()
    
    # 4. Сохраняем в кэш
    redis_client.setex(cache_key, 3600, answer_text)

    return schemas.AnswerResponse(answer=answer_text, sources=sources)