# Используем легкий Linux с Python 3.10
FROM python:3.10-slim

# Делаем рабочую папку внутри контейнера
WORKDIR /app

# Устанавливаем системные библиотеки (нужны для PostgreSQL)
RUN apt-get update && apt-get install -y gcc libpq-dev

# Копируем файл зависимостей и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь наш код внутрь
COPY . .

# Говорим, как запускать приложение
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]