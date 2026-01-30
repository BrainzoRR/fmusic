# bot.py
import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем токен из переменной окружения
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

# Папка для временных файлов
TEMP_DIR = 'temp_audio'
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение"""
    await update.message.reply_text(
        '🎵 Привет! Я бот для скачивания музыки с YouTube.\n\n'
        'Просто напишите название песни и исполнителя, например:\n'
        '"Coldplay - Yellow"\n\n'
        'Я найду несколько вариантов, вы выберете нужный, '
        'и я скачаю полный трек для вас!'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка по командам"""
    await update.message.reply_text(
        '📖 Как пользоваться ботом:\n\n'
        '1. Напишите название песни и исполнителя\n'
        '2. Выберите нужный трек из списка\n'
        '3. Дождитесь скачивания\n'
        '4. Получите полную песню!\n\n'
        'Команды:\n'
        '/start - Начать работу\n'
        '/help - Показать эту справку\n\n'
        '⚠️ Скачивание может занять некоторое время.'
    )

def search_youtube(query, max_results=5):
    """Поиск видео на YouTube"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'skip_download': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(f'ytsearch{max_results}:{query}', download=False)
            
            if search_results and 'entries' in search_results:
                results = []
                for entry in search_results['entries']:
                    if entry:
                        results.append({
                            'id': entry.get('id'),
                            'title': entry.get('title'),
                            'duration': entry.get('duration', 0),
                            'url': f"https://www.youtube.com/watch?v={entry.get('id')}"
                        })
                return results
    except Exception as e:
        logger.error(f'Ошибка поиска на YouTube: {e}')
    
    return []

def format_duration(seconds):
    """Форматирование длительности"""
    if not seconds:
        return 'Неизвестно'
    minutes = seconds // 60
    secs = seconds % 60
    return f'{minutes}:{secs:02d}'

async def search_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск музыки по запросу"""
    query = update.message.text
    
    search_msg = await update.message.reply_text(f'🔍 Ищу: {query}...')
    
    try:
        results = search_youtube(query)
        
        if results:
            keyboard = []
            for i, track in enumerate(results):
                duration = format_duration(track['duration'])
                button_text = f"{i+1}. {track['title'][:50]}... ({duration})"
                keyboard.append([InlineKeyboardButton(
                    button_text, 
                    callback_data=f"download_{track['id']}"
                )])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await search_msg.edit_text(
                f'🎵 Найдено {len(results)} треков по запросу:\n'
                f'"{query}"\n\n'
                'Выберите нужный трек:',
                reply_markup=reply_markup
            )
        else:
            await search_msg.edit_text(
                f'❌ Ничего не найдено по запросу: {query}\n'
                'Попробуйте изменить запрос.'
            )
    
    except Exception as e:
        logger.error(f'Ошибка при поиске: {e}')
        await search_msg.edit_text(
            '❌ Произошла ошибка при поиске.\n'
            'Попробуйте ещё раз позже.'
        )

async def download_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скачивание и отправка музыки"""
    query = update.callback_query
    await query.answer()
    
    video_id = query.data.replace('download_', '')
    video_url = f'https://www.youtube.com/watch?v={video_id}'
    
    await query.edit_message_text('⏬ Скачиваю трек... Это может занять несколько минут.')
    
    output_path = os.path.join(TEMP_DIR, f'{video_id}.mp3')
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(TEMP_DIR, f'{video_id}.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            title = info.get('title', 'Unknown')
            uploader = info.get('uploader', 'Unknown')
            duration = info.get('duration', 0)
        
        await query.edit_message_text('📤 Отправляю трек...')
        
        if os.path.exists(output_path):
            with open(output_path, 'rb') as audio:
                await context.bot.send_audio(
                    chat_id=query.message.chat_id,
                    audio=audio,
                    title=title,
                    performer=uploader,
                    duration=duration,
                    caption=f'🎵 {title}'
                )
            
            await query.edit_message_text('✅ Трек успешно отправлен!')
            
            try:
                os.remove(output_path)
            except:
                pass
        else:
            await query.edit_message_text('❌ Ошибка: файл не найден после скачивания.')
    
    except Exception as e:
        logger.error(f'Ошибка при скачивании: {e}')
        await query.edit_message_text(
            '❌ Произошла ошибка при скачивании.\n'
            'Попробуйте другой трек или повторите позже.'
        )
        
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass

def main():
    """Запуск бота"""
    if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        logger.error('Ошибка: не установлен BOT_TOKEN!')
        logger.error('Установите переменную окружения BOT_TOKEN или измените её в коде')
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_music))
    application.add_handler(CallbackQueryHandler(download_and_send))
    
    logger.info('Бот запущен!')
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

# ===== requirements.txt =====
# python-telegram-bot==21.0.1
# yt-dlp==2024.3.10

# ===== Dockerfile =====
# FROM python:3.11-slim
# 
# WORKDIR /app
# 
# # Установка системных зависимостей
# RUN apt-get update && apt-get install -y \
#     ffmpeg \
#     && rm -rf /var/lib/apt/lists/*
# 
# # Копирование файлов
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt
# 
# COPY bot.py .
# 
# # Создание директории для временных файлов
# RUN mkdir -p temp_audio
# 
# CMD ["python", "bot.py"]

# ===== docker-compose.yml =====
# version: '3.8'
# 
# services:
#   bot:
#     build: .
#     environment:
#       - BOT_TOKEN=${BOT_TOKEN}
#     volumes:
#       - ./temp_audio:/app/temp_audio
#     restart: unless-stopped

# ===== .env.example =====
# BOT_TOKEN=your_bot_token_here

# ===== start.sh (для обычного хостинга) =====
# #!/bin/bash
# 
# # Установка зависимостей
# sudo apt-get update
# sudo apt-get install -y python3 python3-pip ffmpeg
# 
# # Установка Python библиотек
# pip3 install -r requirements.txt
# 
# # Запуск бота
# export BOT_TOKEN="YOUR_BOT_TOKEN_HERE"
# python3 bot.py