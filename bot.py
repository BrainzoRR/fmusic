# bot.py - Улучшенный Telegram Music Bot
import logging
import os
import imageio_ffmpeg
import re
import traceback
import requests
import json
from io import BytesIO
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InlineQueryResultCachedAudio, InputTextMessageContent
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, InlineQueryHandler, filters, ContextTypes
import yt_dlp
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggvorbis import OggVorbis

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')

TEMP_DIR = 'temp_audio'
CACHE_FILE = 'track_cache.json'

if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# Загрузка кэша из файла
def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_cache(cache):
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Cache save error: {e}")

TRACK_CACHE = load_cache()

# Настройки пользователей (качество аудио)
USER_SETTINGS = {}

# === УМНЫЙ ПАРСИНГ НАЗВАНИЙ ===
def clean_title(title):
    """Убирает весь мусор из названия"""
    if not title:
        return "Unknown Track"
    
    # Убираем всё после | или - если там есть "Official", "Audio", "Video" и т.д.
    title = re.sub(r'\s*[\|\-]\s*(Official\s*(Music\s*)?(Video|Audio|Lyric Video)|Lyrics?|HD|4K|Music\s*Video|Audio|MV).*$', '', title, flags=re.IGNORECASE)
    
    # Убираем (Official...), [Official...], и т.д.
    title = re.sub(r'\s*[\(\[\{]\s*(Official|Audio|Video|Lyric|Music|HD|4K|MV|Премьера|Клип).*?[\)\]\}]', '', title, flags=re.IGNORECASE)
    
    # Убираем годы в конце (2023), [2024] и т.д.
    title = re.sub(r'\s*[\(\[\{]?\s*(19|20)\d{2}\s*[\)\]\}]?\s*$', '', title)
    
    # Убираем лишние пробелы
    title = re.sub(r'\s+', ' ', title).strip()
    
    return title if title else "Unknown Track"

def parse_artist_title(full_title, uploader):
    """Парсит исполнителя и название из заголовка"""
    # Очищаем от мусора
    full_title = clean_title(full_title)
    
    # Типичные форматы: "Artist - Title" или "Artist — Title"
    if ' - ' in full_title or ' – ' in full_title or ' — ' in full_title:
        parts = re.split(r'\s*[-–—]\s*', full_title, maxsplit=1)
        if len(parts) == 2:
            artist = parts[0].strip()
            title = parts[1].strip()
            
            # Убираем "Topic" из исполнителя
            artist = re.sub(r'\s*-\s*Topic\s*$', '', artist, flags=re.IGNORECASE)
            artist = artist.replace(' Topic', '').strip()
            
            return artist, title
    
    # Если нет разделителя, используем uploader как артиста
    uploader_clean = uploader.replace(' - Topic', '').replace(' Topic', '').strip()
    uploader_clean = re.sub(r'\s*-\s*Topic\s*$', '', uploader_clean, flags=re.IGNORECASE)
    
    return uploader_clean, full_title

# === НАСТРОЙКИ ЗАГРУЗЧИКА ===
def get_ydl_opts(is_download=False, filepath=None, quality='best'):
    """Настройки yt-dlp с поддержкой выбора качества"""
    
    # Получаем путь к ffmpeg из библиотеки
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

    opts = {
        'quiet': True,
        'no_warnings': True,
        'ffmpeg_location': ffmpeg_path,  # <--- ЯВНО УКАЗЫВАЕМ ПУТЬ
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'player_skip': ['webpage', 'configs']
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
    }
    
    if is_download:
        # Выбор качества
        if quality == 'high':
            opts['format'] = 'bestaudio[abr>=256]/bestaudio/best'
        elif quality == 'medium':
            opts['format'] = 'bestaudio[abr>=128][abr<=192]/bestaudio/best'
        else:  # low
            opts['format'] = 'bestaudio[abr<=128]/worstaudio/best'
            
        opts['writethumbnail'] = True
        opts['outtmpl'] = filepath
        opts['extract_flat'] = False
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }]
    else:
        opts['extract_flat'] = True
        opts['skip_download'] = True
        
    return opts

# === КОМАНДА START ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot_username = (await context.bot.get_me()).username
    
    welcome_text = f'''🎵 <b>Добро пожаловать в Music Bot!</b>

Привет, {user.first_name}! 👋

<b>📖 Как пользоваться:</b>

<b>1️⃣ В личке или группе:</b>
/find название песни - поиск музыки

<b>2️⃣ В любом чате (inline режим):</b>
@{bot_username} название песни
<i>Результаты появятся прямо в чате!</i>

<b>⚙️ Дополнительно:</b>
/settings - настроить качество аудио
/help - помощь и примеры
/stats - твоя статистика

<b>💡 Примеры:</b>
• /find Imagine Dragons Believer
• /find Shape of You
• @{bot_username} Bohemian Rhapsody

<i>❗ Для inline режима убедитесь, что он включен в @BotFather!</i>

<b>🎧 Приятного прослушивания!</b>'''
    
    keyboard = [
        [InlineKeyboardButton("⚙️ Настройки качества", callback_data="settings")],
        [InlineKeyboardButton("📊 Моя статистика", callback_data="stats")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Проверяем, это обычное сообщение или callback
    if update.message:
        await update.message.reply_html(welcome_text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(welcome_text, parse_mode='HTML', reply_markup=reply_markup)

# === ПОМОЩЬ ===
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = (await context.bot.get_me()).username
    
    help_text = f'''❓ <b>Справка по использованию</b>

<b>🔍 Поиск музыки:</b>
/find [название] - поиск треков
Пример: <code>/find The Weeknd Blinding Lights</code>

<b>🌐 Inline режим (в любом чате):</b>
@{bot_username} [название]
Пример: <code>@{bot_username} Dua Lipa Levitating</code>

<b>⚙️ Настройки:</b>
/settings - выбрать качество аудио
• 🔥 High (256+ kbps) - лучшее
• ⚡ Medium (128-192 kbps) - баланс
• 💾 Low (<128 kbps) - экономия

<b>📊 Статистика:</b>
/stats - сколько треков скачал

<b>🎯 Советы:</b>
• Пишите название и исполнителя для точности
• Используйте inline для быстрого поиска
• Кэшированные треки отправляются мгновенно

<b>⚡ Лимиты:</b>
20 треков в час на пользователя'''
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_start")]]
    
    if update.message:
        await update.message.reply_html(help_text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        try:
            await update.callback_query.edit_message_text(help_text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            # Если сообщение не изменилось - ничего страшного
            pass

# === НАСТРОЙКИ ===
async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current = USER_SETTINGS.get(user_id, 'high')
    
    quality_names = {"high": "🔥 High", "medium": "⚡ Medium", "low": "💾 Low"}
    
    text = f'''⚙️ <b>Настройки качества аудио</b>

Текущее: <b>{quality_names.get(current)}</b>

Выберите качество:'''
    
    keyboard = [
        [InlineKeyboardButton(
            f"{'✅ ' if current == 'high' else ''}🔥 High (256+ kbps)", 
            callback_data="quality_high"
        )],
        [InlineKeyboardButton(
            f"{'✅ ' if current == 'medium' else ''}⚡ Medium (128-192 kbps)", 
            callback_data="quality_medium"
        )],
        [InlineKeyboardButton(
            f"{'✅ ' if current == 'low' else ''}💾 Low (<128 kbps)", 
            callback_data="quality_low"
        )],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_start")]
    ]
    
    if update.message:
        await update.message.reply_html(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        try:
            await update.callback_query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            # Если сообщение не изменилось - ничего страшного
            pass

# === СТАТИСТИКА ===
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = context.user_data
    
    downloads = user_data.get('downloads', 0)
    searches = user_data.get('searches', 0)
    
    quality_names = {"high": "🔥 High", "medium": "⚡ Medium", "low": "💾 Low"}
    current_quality = quality_names.get(USER_SETTINGS.get(user_id, 'high'))
    
    text = f'''📊 <b>Твоя статистика</b>

⬇️ Скачано треков: <b>{downloads}</b>
🔍 Поисков: <b>{searches}</b>
⚙️ Качество: <b>{current_quality}</b>

💡 Продолжай в том же духе!'''
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back_start")]]
    
    if update.message:
        await update.message.reply_html(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        try:
            await update.callback_query.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception:
            # Если сообщение не изменилось - ничего страшного
            pass

# === ПОИСК ===
def search_youtube(query, max_results=10):
    try:
        with yt_dlp.YoutubeDL(get_ydl_opts(is_download=False)) as ydl:
            res = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            return res.get('entries', [])
    except Exception as e:
        logger.error(f"Search Error: {e}")
        return []

def format_duration(seconds):
    if not seconds: return '?:??'
    s = int(seconds)
    return f'{s // 60}:{s % 60:02d}'

def download_thumbnail(url, video_id):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            img_path = os.path.join(TEMP_DIR, f'{video_id}_thumb.jpg')
            img = Image.open(BytesIO(response.content))
            if img.mode != 'RGB': 
                img = img.convert('RGB')
            img.save(img_path, 'JPEG', quality=90)
            return img_path
    except: 
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
    except Exception as e:
        logger.error(f"Metadata error: {e}")

# === СКАЧИВАНИЕ И ОТПРАВКА ===
async def download_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    data = query.data
    if not data.startswith('dl_'): 
        return

    user_id = query.from_user.id
    video_id = data.replace('dl_', '')
    video_url = f'https://www.youtube.com/watch?v={video_id}'
    
    # Проверка лимита
    user_data = context.user_data
    hour_key = f"downloads_{user_id}_{__import__('datetime').datetime.now().hour}"
    hourly_count = user_data.get(hour_key, 0)
    
    if hourly_count >= 20:
        try:
            await query.edit_message_text('⏳ Лимит: 20 треков в час. Подожди немного!')
            return
        except:
            return
    
    try:
        await query.edit_message_text('⬇️ <b>Скачиваю...</b>', parse_mode='HTML')
    except: 
        pass
    
    quality = USER_SETTINGS.get(user_id, 'high')
    filepath_tmpl = os.path.join(TEMP_DIR, f'{video_id}.%(ext)s')
    
    try:
        # Не забываем про imageio_ffmpeg, если ты его добавил
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        
        # Обновляем опции, добавляем путь к ffmpeg
        opts = get_ydl_opts(is_download=True, filepath=filepath_tmpl, quality=quality)
        opts['ffmpeg_location'] = ffmpeg_path  # Явно указываем путь

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            
            # --- ИСПРАВЛЕНИЕ ТУТ ---
            # Мы жестко задаем имя файла, так как точно знаем, что конвертируем в m4a
            final_filename = os.path.join(TEMP_DIR, f"{video_id}.m4a")
            # -----------------------
            
            full_title = info.get('title', 'Unknown')
            uploader = info.get('uploader', 'Unknown Artist')
            duration = info.get('duration', 0)
            thumb_url = info.get('thumbnail')
            
            # УМНЫЙ ПАРСИНГ
            artist, title = parse_artist_title(full_title, uploader)

        thumb_path = download_thumbnail(thumb_url, video_id) if thumb_url else None
        
        # Добавим лог, чтобы видеть, нашел ли бот файл
        if os.path.exists(final_filename):
            add_metadata_and_cover(final_filename, title, artist, thumb_path)
            
            if query.message:
                chat_id = query.message.chat_id
                success_text = '✅ <b>Отправлено!</b>'
            else:
                chat_id = user_id
                success_text = '✅ <b>Отправлено в личку!</b>'
                try:
                    await query.edit_message_text('📩 <b>Отправил трек тебе в ЛС!</b>', parse_mode='HTML')
                except: 
                    pass

            with open(final_filename, 'rb') as audio:
                t_data = open(thumb_path, 'rb').read() if thumb_path else None
                
                msg = await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=audio,
                    thumbnail=t_data,
                    title=title,
                    performer=artist,
                    duration=duration,
                    caption=f'🎵 <b>{title}</b>\n👤 {artist}',
                    parse_mode='HTML'
                )
                
                if msg.audio:
                    TRACK_CACHE[video_id] = {
                        'file_id': msg.audio.file_id,
                        'title': title,
                        'artist': artist
                    }
                    save_cache(TRACK_CACHE)

            # Статистика
            user_data['downloads'] = user_data.get('downloads', 0) + 1
            user_data[hour_key] = hourly_count + 1

            try:
                if query.message:
                    await query.edit_message_text(success_text, parse_mode='HTML')
            except: 
                pass
            
            # Очистка
            if os.path.exists(final_filename):
                os.remove(final_filename)
            if thumb_path and os.path.exists(thumb_path):
                os.remove(thumb_path)
        else:
            # Если файл не найден - сообщаем об ошибке
            logger.error(f"File not found: {final_filename}")
            await query.edit_message_text('❌ Ошибка: файл скачался, но потерялся.', parse_mode='HTML')
            
    except Exception as e:
        logger.error(f"Download Error: {e}\n{traceback.format_exc()}")
        try:
            await query.edit_message_text('❌ Ошибка загрузки. Попробуй другой трек.', parse_mode='HTML')
        except: 
            pass

# === INLINE РЕЖИМ ===
async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    if not query: 
        return
    
    user_data = context.user_data
    user_data['searches'] = user_data.get('searches', 0) + 1
    
    results = search_youtube(query, max_results=15)
    articles = []
    
    for r in results:
        vid = r['id']
        full_title = r.get('title', 'Unknown')
        uploader = r.get('uploader', 'Unknown')
        duration = format_duration(r.get('duration'))
        
        # Парсим название
        artist, title = parse_artist_title(full_title, uploader)
        display_title = f"{artist} - {title}"
        
        if vid in TRACK_CACHE:
            cache_data = TRACK_CACHE[vid]
            articles.append(InlineQueryResultCachedAudio(
                id=vid,
                audio_file_id=cache_data['file_id'],
                caption=f"🎵 {cache_data['title']}\n👤 {cache_data['artist']}"
            ))
        else:
            articles.append(InlineQueryResultArticle(
                id=vid,
                title=display_title,
                description=f"⏱ {duration} • 👤 {artist}",
                thumbnail_url=r.get('thumbnail'),
                input_message_content=InputTextMessageContent(
                    f"🎵 <b>{title}</b>\n👤 {artist}\n\n👇 Нажми кнопку для скачивания!",
                    parse_mode='HTML'
                ),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬇️ Скачать", callback_data=f"dl_{vid}")
                ]])
            ))
            
    await update.inline_query.answer(articles, cache_time=5)

# === КОМАНДА FIND ===
async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_html(
            '❓ <b>Использование:</b>\n/find название песни\n\n'
            '<b>Пример:</b>\n<code>/find Imagine Dragons Believer</code>'
        )
        return
    
    user_data = context.user_data
    user_data['searches'] = user_data.get('searches', 0) + 1
    
    msg = await update.message.reply_text("🔎 Ищу...")
    results = search_youtube(" ".join(context.args), max_results=5)
    
    if not results:
        await msg.edit_text("😔 Ничего не найдено. Попробуй изменить запрос.")
        return

    kb = []
    for r in results:
        artist, title = parse_artist_title(r.get('title', ''), r.get('uploader', ''))
        duration = format_duration(r.get('duration'))
        display = f"🎵 {artist} - {title} ({duration})"
        kb.append([InlineKeyboardButton(display[:60], callback_data=f"dl_{r['id']}")])
    
    kb.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    
    await msg.edit_text("🎯 <b>Результаты поиска:</b>", parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))

# === CALLBACK ОБРАБОТЧИКИ ===
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    # Отвечаем на callback чтобы убрать "часики"
    await query.answer()
    
    if data.startswith('dl_'):
        await download_and_send(update, context)
    elif data == 'settings':
        await settings_command(update, context)
    elif data == 'stats':
        await stats_command(update, context)
    elif data == 'help':
        await help_command(update, context)
    elif data.startswith('quality_'):
        quality = data.replace('quality_', '')
        USER_SETTINGS[query.from_user.id] = quality
        await query.answer(f"✅ Качество изменено на {quality.upper()}!", show_alert=True)
        await settings_command(update, context)
    elif data == 'back_start':
        await start(update, context)
    elif data == 'cancel':
        try:
            await query.edit_message_text("❌ Отменено")
        except:
            pass

# === НОВЫЙ УЧАСТНИК ===
async def new_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for m in update.message.new_chat_members:
        if m.id == context.bot.id:
            bot_username = (await context.bot.get_me()).username
            await update.message.reply_html(
                f'👋 <b>Привет! Я музыкальный бот!</b>\n\n'
                f'Используй /find или @{bot_username} для поиска музыки\n'
                f'Команды: /help'
            )

def main():
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN не установлен!")
        return
        
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("find", find_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(InlineQueryHandler(inline_query))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_chat_member))
    
    print("✅ Бот запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
