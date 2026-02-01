# bot.py
import logging
import os
import traceback
import requests
from io import BytesIO
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InlineQueryResultCachedAudio, InputTextMessageContent
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

BOT_TOKEN = os.getenv('BOT_TOKEN')

TEMP_DIR = 'temp_audio'
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# КЭШ: video_id -> file_id
TRACK_CACHE = {}

# === НАСТРОЙКИ ЗАГРУЗЧИКА ===
def get_ydl_opts(is_download=False, filepath=None):
    opts = {
        'quiet': True,
        'no_warnings': True,
        # ВАЖНО: Эти настройки спасают от ошибки 403
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
        opts['format'] = 'bestaudio/best'
        opts['writethumbnail'] = True
        opts['outtmpl'] = filepath
        opts['extract_flat'] = False
    else:
        opts['extract_flat'] = True
        opts['skip_download'] = True
        
    return opts

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = (await context.bot.get_me()).username
    txt = (
        f'👋 <b>Привет!</b>\n\n'
        f'1️⃣ <b>В чате:</b> /find песня\n'
        f'2️⃣ <b>Везде:</b> @{bot_username} песня\n\n'
        f'<i>Если @ поиск не работает — включи Inline Mode в BotFather!</i>'
    )
    await update.message.reply_html(txt)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Просто напиши /find название")

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
            if img.mode != 'RGB': img = img.convert('RGB')
            img.save(img_path, 'JPEG', quality=90)
            return img_path
    except: return None

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
            if thumbnail_path:
                p = Picture()
                p.type = 3
                with open(thumbnail_path, 'rb') as f: p.data = f.read()
                p.mime = 'image/jpeg'
                audio['metadata_block_picture'] = [p]
            audio.save()
    except: pass

# === СКАЧИВАНИЕ И ОТПРАВКА ===
async def download_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if not data.startswith('dl_'): return

    video_id = data.replace('dl_', '')
    video_url = f'https://www.youtube.com/watch?v={video_id}'
    
    try:
        await query.edit_message_text('⏬ *Скачиваю...*', parse_mode='Markdown')
    except: pass
    
    filepath_tmpl = os.path.join(TEMP_DIR, f'{video_id}.%(ext)s')
    
    try:
        # Скачиваем с рабочими настройками
        opts = get_ydl_opts(is_download=True, filepath=filepath_tmpl)
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            final_filename = ydl.prepare_filename(info)
            title = info.get('title', 'Track')
            uploader = info.get('uploader', 'Artist')
            duration = info.get('duration', 0)
            thumb_url = info.get('thumbnail')

        thumb_path = download_thumbnail(thumb_url, video_id) if thumb_url else None
        
        if os.path.exists(final_filename):
            add_metadata_and_cover(final_filename, title, uploader, thumb_path)
            
            # === ВОТ ЗДЕСЬ БЫЛА ОШИБКА, ТЕПЕРЬ ИСПРАВЛЕНО ===
            if query.message:
                # Если нажали кнопку в обычном чате (/find)
                chat_id = query.message.chat_id
                success_text = '✅ *Отправлено!*'
            else:
                # Если нажали кнопку в Inline режиме (@bot)
                # У нас нет ID чата, поэтому отправляем в ЛИЧКУ тому, кто нажал
                chat_id = query.from_user.id
                success_text = '✅ *Отправлено в личку!*'
                try:
                    await query.edit_message_text('📩 *Отправил трек тебе в ЛС!*', parse_mode='Markdown')
                except: pass

            # Отправка файла
            with open(final_filename, 'rb') as audio:
                t_data = open(thumb_path, 'rb').read() if thumb_path else None
                
                msg = await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=audio,
                    thumbnail=t_data,
                    title=title,
                    performer=uploader,
                    duration=duration,
                    caption=f'🎵 *{title}*\n👤 {uploader}',
                    parse_mode='Markdown'
                )
                
                # Сохраняем в кэш! В следующий раз поиск через @ выдаст файл сразу.
                if msg.audio:
                    TRACK_CACHE[video_id] = msg.audio.file_id

            try:
                if query.message:
                    await query.edit_message_text(success_text, parse_mode='Markdown')
            except: pass
            
            # Удаляем временные файлы
            os.remove(final_filename)
            if thumb_path: os.remove(thumb_path)
            
    except Exception as e:
        logger.error(f"Download Error: {e}\n{traceback.format_exc()}")
        try:
            await query.edit_message_text('❌ Ошибка. Если вы в Inline режиме, убедитесь, что вы запустили бота в личке.', parse_mode='Markdown')
        except: pass

# === INLINE ===
async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.inline_query.query
    if not query: return
    
    results = search_youtube(query)
    articles = []
    
    for r in results:
        vid = r['id']
        title = r['title']
        
        # Если есть в кэше — кидаем как музыку (можно сразу в любой чат)
        if vid in TRACK_CACHE:
            articles.append(InlineQueryResultCachedAudio(
                id=vid,
                audio_file_id=TRACK_CACHE[vid],
                caption=f"🎵 {title}"
            ))
        else:
            # Если нет — кнопка скачать
            articles.append(InlineQueryResultArticle(
                id=vid,
                title=title,
                description="Нажми, чтобы скачать",
                thumbnail_url=r.get('thumbnail'),
                input_message_content=InputTextMessageContent(f"🎵 {title}\n👇 Жми кнопку!"),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬇️ Скачать", callback_data=f"dl_{vid}")]])
            ))
            
    await update.inline_query.answer(articles, cache_time=5)

async def find_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    msg = await update.message.reply_text("🔎 Ищу...")
    results = search_youtube(" ".join(context.args), max_results=5)
    
    if not results:
        await msg.edit_text("Ничего не найдено.")
        return

    kb = []
    for r in results:
        kb.append([InlineKeyboardButton(f"{r['title'][:40]}", callback_data=f"dl_{r['id']}")])
    
    await msg.edit_text("Результаты:", reply_markup=InlineKeyboardMarkup(kb))

async def new_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for m in update.message.new_chat_members:
        if m.id == context.bot.id:
            await update.message.reply_text("Привет! Я музыкальный бот.")

def main():
    if not BOT_TOKEN: return
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("find", find_command))
    app.add_handler(InlineQueryHandler(inline_query))
    app.add_handler(CallbackQueryHandler(download_and_send))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_chat_member))
    
    print("Бот запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
