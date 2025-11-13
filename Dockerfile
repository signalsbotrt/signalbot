# 1. Базовый Python образ
FROM python:3.11-slim

# 2. Устанавливаем рабочую директорию
WORKDIR /app

# 3. Копируем только нужные файлы
COPY requirements.txt .
COPY main.py .
COPY pyproject.toml .
COPY Procfile .

# 4. Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt
 
# 5. Копируем всё остальное (например, если появятся новые файлы)
COPY .  .

# 6. Указываем команду запуска
CMD ["python", "main.py"]
