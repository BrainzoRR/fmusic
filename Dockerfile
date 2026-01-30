FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей включая FFmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Проверка установки FFmpeg
RUN ffmpeg -version

# Копирование файла зависимостей
COPY requirements.txt .

# Установка Python библиотек
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование кода бота
COPY bot.py .

# Создание директории для временных файлов
RUN mkdir -p temp_audio && chmod 777 temp_audio

# Запуск бота
CMD ["python", "-u", "bot.py"]
