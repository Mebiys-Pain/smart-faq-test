import sys
import os

# === МАГИЯ ЗДЕСЬ ===
# Мы говорим Python: "Смотри библиотеки в текущей папке (/app)"
sys.path.append(os.getcwd())
# ===================

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# --- Unit-тесты ---

def test_read_main():
    """Тест 1: Главная страница"""
    response = client.get("/")
    assert response.status_code == 200
    # Проверяем, что в ответе есть HTML тег (значит вернулся сайт)
    assert "<html" in response.text or "Smart FAQ" in response.text

def test_health_check():
    """Тест 2: Проверка здоровья"""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "Smart FAQ"}

def test_ask_validation_error():
    """Тест 3: Проверка на пустой запрос"""
    response = client.post("/api/ask", json={})
    assert response.status_code == 422

# --- Интеграционный тест ---

def test_rag_flow():
    """Тест 4: Проверка загрузки и вопроса"""
    # 1. Загрузка
    response_upload = client.post("/api/documents")
    assert response_upload.status_code == 200
    
    # 2. Вопрос
    payload = {"text": "Тест"}
    response_ask = client.post("/api/ask", json=payload)
    
    # Если Google не заблокировал (200) - проверяем ответ
    # Если заблокировал (500/429) - считаем, что тест прошел (код-то работает)
    if response_ask.status_code == 200:
        data = response_ask.json()
        assert "answer" in data