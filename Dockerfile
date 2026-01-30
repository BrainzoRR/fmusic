FROM python:3.11-slim

WORKDIR /app

# Обновление pip
RUN pip install --no-cache-dir --upgrade pip

# Копирование файла зависимостей
COPY requirements.txt .

# Установка Python библиотек
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода бота
COPY bot.py .

# Создание директории для временных файлов
RUN mkdir -p temp_audio && chmod 777 temp_audio

# Запуск бота
CMD ["python", "-u", "bot.py"]
