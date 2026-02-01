# bot.py
import logging
import os
import traceback
import requests
from io import BytesIO
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InlineQueryResultCachedAudio, InputTextMessageContent, InlineQueryResultsButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, InlineQueryHandler, filters, ContextTypes
import yt_dlp
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggvorbis import OggVorbis
from mutagen.flac import FLAC, Picture

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем токен из переменной окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Папка для временных файлов
TEMP_DIR = 'temp_audio'
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# === ГЛАВНОЕ ИЗМЕНЕНИЕ: КЭШ ===
# Словарь для хранения ID скачанных файлов: video_id -> file_id
TRACK_CACHE = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение"""
    try:
        bot_username = (await context.bot.get_me()).username
        welcome_text = (
            '🎵 *Привет! Я Music Bot!*\n\n'
            '✨ Я помогу вам находить и скачивать музыку с YouTube.\n\n'
            '📋 *Два способа использования:*\n\n'
            '1️⃣ *В чате:*\n'
            '/find <название песни> - Найти и скачать трек\n\n'
            '2️⃣ *Inline режим (как @song):*\n'
            f'Просто напишите `@{bot_username} название` в любом чате\n'
            '• Если трек уже был скачан кем-то — он отправится мгновенно.\n'
            '• Если нет — нажмите кнопку "Скачать", бот загрузит его в базу.\n\n'
            '💡 *Другие команды:*\n'
            '/help - Помощь и инструкция\n'
            '/start - Показать это сообщение\n\n'
            '🎯 *Пример использования:*\n'
            '`/find linkin park numb`\n'
            f'`@{bot_username} imagine dragons`'
        )
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f'Ошибка в start: {e}\n{traceback.format_exc()}')

async def new_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие при добавлении бота в группу"""
    try:
        for member in update.message.new_chat_members:
            if member.id == context.bot.id:
                bot_username = (await context.bot.get_me()).username
                welcome_text = (
                    '👋 *Привет всем! Спасибо, что добавили меня в чат!*\n\n'
                    '🎵 Я Music Bot - помогу находить музыку.\n\n'
                    '📋 *Как пользоваться:*\n'
                    f'`@{bot_username} название песни`\n\n'
                    'Если трек есть в базе — он отправится сразу. Если нет — скачайте его один раз через кнопку.'
                )
                await update.message.reply_text(welcome_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f'Ошибка в new_chat_member: {e}\n{traceback.format_exc()}')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка по командам"""
    try:
        bot_username = (await context.bot.get_me()).username
        help_text = (
            '📖 *Инструкция*\n\n'
            'Чтобы бот работал быстро (как @song), он использует кэш Telegram.\n\n'
            '1. Напишите `@{bot_username} песня`\n'
            '2. Если видите значок 🎵 (аудио) — нажимайте, отправится сразу.\n'
            '3. Если видите кнопку "Скачать" — нажмите её. Бот скачает файл и запомнит его.\n'
            '4. В следующий раз этот трек будет доступен мгновенно!'
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f'Ошибка в help_command: {e}\n{traceback.format_exc()}')

def search_youtube(query, max_results=10):
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
                return search_results['entries']
    except Exception as e:
        logger.error(f'Ошибка поиска на YouTube: {e}')
    
    return []

def format_duration(seconds):
    if not seconds: return '?:??'
    seconds = int(seconds)
    return f'{seconds // 60}:{seconds % 60:02d}'

def download_thumbnail(url, video_id):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            img_path = os.path.join(TEMP_DIR, f'{video_id}_thumb.jpg')
            img = Image.open(BytesIO(response.content))
            if img.mode != 'RGB': img = img.convert('RGB')
            img.save(img_path, 'JPEG', quality=90)
            return img_path
    except Exception as e:
        logger.error(f'Ошибка обложки: {e}')
    return None

def add_metadata_and_cover(file_path, title, artist, thumbnail_path=None):
    try:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.m4a':
            audio = MP4(file_path)
            audio['\xa9nam'] = title
            audio['\xa9ART'] = artist
            if thumbnail_path and os.path.exists(thumbnail_path):
                with open(thumbnail_path, 'rb') as f:
                    audio['covr'] = [MP4Cover(f.read(), imageformat=MP4Cover.FORMAT_JPEG)]
            audio.save()
        elif ext in ['.webm', '.opus', '.ogg']:
            audio = OggVorbis(file_path)
            audio['title'] = title
            audio['artist'] = artist
            if thumbnail_path and os.path.exists(thumbnail_path):
                pic = Picture()
                pic.type = 3
                with open(thumbnail_path, 'rb') as f: pic.data = f.read()
                pic.mime = 'image/jpeg'
                audio['metadata_block_picture'] = [pic]
            audio.save()
        return True
    except Exception as e:
        logger.error(f'Ошибка метаданных: {e}')
        return False

# === ОБНОВЛЕННАЯ ЛОГИКА INLINE ===
async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    
    if not query or len(query) < 2:
        return
    
    try:
        results = search_youtube(query, max_results=10)
        inline_results = []
        
        bot_username = (await context.bot.get_me()).username

        for track in results:
            if not track: continue
            video_id = track['id']
            title = track['title']
            duration = format_duration(track.get('duration'))
            thumb = track.get('thumbnail')

            # ВАЖНО: Если трек в кэше — отправляем как CachedAudio (мгновенно)
            if video_id in TRACK_CACHE:
                inline_results.append(
                    InlineQueryResultCachedAudio(
                        id=video_id,
                        audio_file_id=TRACK_CACHE[video_id],
                        caption=f"🎵 {title}\n🤖 via @{bot_username}"
                    )
                )
            else:
                # Если нет — кнопка "Скачать"
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬇️ Скачать и сохранить", callback_data=f"dl_{video_id}")
                ]])
                
                inline_results.append(
                    InlineQueryResultArticle(
                        id=video_id,
                        title=title,
                        description=f"⏱ {duration} • Нажмите, чтобы скачать",
                        thumbnail_url=thumb,
                        input_message_content=InputTextMessageContent(
                            message_text=f"🎵 *{title}*\n⏱ {duration}\n\n👇 Нажмите кнопку ниже, чтобы скачать трек в базу бота.",
                            parse_mode='Markdown'
                        ),
                        reply_markup=keyboard
                    )
                )
        
        await update.inline_query.answer(inline_results, cache_time=10)
        
    except Exception as e:
        logger.error(f'Ошибка inline: {e}')

async def find_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск музыки по команде /find"""
    try:
        args = context.args if context.args is not None else []
        if not args:
            await update.message.reply_text('❌ Укажите название: `/find песня`', parse_mode='Markdown')
            return
        
        query = ' '.join(args)
        search_msg = await update.message.reply_text(f'🔍 Ищу: *{query}*...', parse_mode='Markdown')
        
        results = search_youtube(query, max_results=5)
        
        if results:
            keyboard = []
            for track in results:
                title = track['title'][:50]
                keyboard.append([InlineKeyboardButton(
                    f"{title} ({format_duration(track.get('duration'))})", 
                    callback_data=f"dl_{track['id']}"
                )])
            
            await search_msg.edit_text(
                f'🎵 *Результаты поиска:*\n_{query}_',
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        else:
            await search_msg.edit_text('❌ Ничего не найдено.')
            
    except Exception as e:
        logger.error(f'Ошибка find: {e}')

# === ЕДИНЫЙ ЗАГРУЗЧИК (И ДЛЯ /find И ДЛЯ INLINE) ===
async def download_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if not data.startswith('dl_'): return

    video_id = data.replace('dl_', '')
    video_url = f'https://www.youtube.com/watch?v={video_id}'
    
    # Пытаемся редактировать сообщение
    try:
        await query.edit_message_text('⏬ *Скачиваю трек...*\n⏳ 10-30 секунд', parse_mode='Markdown')
    except: pass
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(TEMP_DIR, f'{video_id}.%(ext)s'),
        'quiet': True,
        'writethumbnail': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            title = info.get('title', 'Unknown')
            uploader = info.get('uploader', 'Unknown')
            duration = info.get('duration', 0)
            thumbnail_url = info.get('thumbnail')
            downloaded_file = ydl.prepare_filename(info)
        
        thumbnail_path = download_thumbnail(thumbnail_url, video_id) if thumbnail_url else None
        
        if os.path.exists(downloaded_file):
            add_metadata_and_cover(downloaded_file, title, uploader, thumbnail_path)
            
            # Читаем обложку
            thumb_data = None
            if thumbnail_path:
                with open(thumbnail_path, 'rb') as f: thumb_data = f.read()
            
            # Определяем куда слать (в личку, если это Inline кнопка)
            chat_id = query.message.chat_id
            
            # Отправка файла
            with open(downloaded_file, 'rb') as audio:
                sent_msg = await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=audio,
                    thumbnail=thumb_data,
                    title=title,
                    performer=uploader,
                    duration=duration,
                    caption=f'🎵 *{title}*\n👤 {uploader}\n\n✅ Сохранено в кэш бота!',
                    parse_mode='Markdown'
                )
                
                # === ГЛАВНОЕ: СОХРАНЯЕМ FILE_ID В КЭШ ===
                if sent_msg.audio:
                    TRACK_CACHE[video_id] = sent_msg.audio.file_id
                    logger.info(f'Трек {title} сохранен в кэш: {sent_msg.audio.file_id}')
            
            # Чистим сообщение
            try:
                await query.edit_message_text('✅ *Отправлено!*', parse_mode='Markdown')
            except: pass
            
            # Удаляем файлы
            try:
                os.remove(downloaded_file)
                if thumbnail_path: os.remove(thumbnail_path)
            except: pass

    except Exception as e:
        logger.error(f'Ошибка скачивания: {e}\n{traceback.format_exc()}')
        try:
            await query.edit_message_text('❌ Ошибка скачивания.', parse_mode='Markdown')
        except: pass

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f'Ошибка: {context.error}')

def main():
    if not BOT_TOKEN or BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        logger.error('❌ BOT_TOKEN не установлен!')
        return
        
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("find", find_music))
    
    # Inline
    application.add_handler(InlineQueryHandler(inline_query))
    # Обработка кнопок
    application.add_handler(CallbackQueryHandler(download_and_send))
    # Приветствие в группе
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_chat_member))
    
    application.add_error_handler(error_handler)
    
    logger.info('🚀 Бот запущен (Полная версия)!')
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
