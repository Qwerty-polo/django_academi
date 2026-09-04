# 1. Беремо легку версію Python
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Вказуємо робочу папку всередині контейнера
WORKDIR /app

# 4. Копіюємо список бібліотек і встановлюємо їх
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# 5. Копіюємо весь наш код у контейнер
COPY . /app/