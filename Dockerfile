FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем Python пакеты
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код бота
COPY bot.py .

# Создаем директорию для временных файлов
RUN mkdir -p temp_audio

# Запуск
CMD ["python", "bot.py"]
