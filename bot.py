# bot.py
import logging
import os
import traceback
import requests
from io import BytesIO
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent, InlineQueryResultsButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, InlineQueryHandler, ChosenInlineResultHandler, filters, ContextTypes
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
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

# Папка для временных файлов
TEMP_DIR = 'temp_audio'
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение"""
    try:
        welcome_text = (
            '🎵 *Привет! Я Music Bot!*\n\n'
            '✨ Я помогу вам находить и скачивать музыку с YouTube.\n\n'
            '📋 *Два способа использования:*\n\n'
            '1️⃣ *В чате:*\n'
            '/find <название песни> - Найти и скачать трек\n\n'
            '2️⃣ *Inline режим (в любом чате):*\n'
            'Просто напишите `@' + (await context.bot.get_me()).username + ' название песни`\n'
            'Пример: `@' + (await context.bot.get_me()).username + ' kijin на скейте`\n\n'
            '💡 *Другие команды:*\n'
            '/help - Помощь и инструкция\n'
            '/start - Показать это сообщение\n\n'
            '🎯 *Пример использования:*\n'
            '`/find kijin на скейте`\n'
            '`/find coldplay yellow`\n\n'
            '✨ С обложками и правильными метаданными!'
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
                    '🎵 Я Music Bot - помогу находить и скачивать музыку.\n\n'
                    '📋 *Два способа использования:*\n\n'
                    '1️⃣ *Команда:*\n'
                    '`/find <название>` - Найти трек\n\n'
                    '2️⃣ *Inline режим:*\n'
                    f'`@{bot_username} название песни`\n\n'
                    '❓ `/help` - Подробная инструкция\n\n'
                    '🎯 *Пример:*\n'
                    '`/find kijin на скейте`\n'
                    f'`@{bot_username} imagine dragons`\n\n'
                    '✅ Готов к работе!'
                )
                await update.message.reply_text(welcome_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f'Ошибка в new_chat_member: {e}\n{traceback.format_exc()}')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка по командам"""
    try:
        bot_username = (await context.bot.get_me()).username
        help_text = (
            '📖 *Инструкция по использованию Music Bot*\n\n'
            '🔍 *Способ 1: Команда /find*\n'
            '1. Напишите `/find` и название песни\n'
            '2. Я найду несколько вариантов\n'
            '3. Выберите нужный трек кнопкой\n'
            '4. Дождитесь скачивания\n'
            '5. Получите трек с обложкой!\n\n'
            '🎯 *Способ 2: Inline режим*\n'
            f'1. В любом чате напишите `@{bot_username} название`\n'
            '2. Выберите трек из списка\n'
            '3. Трек появится в чате с пометкой via @' + bot_username + '\n\n'
            '📋 *Команды:*\n'
            '`/find <название>` - Найти трек\n'
            '`/help` - Эта справка\n'
            '`/start` - Приветствие\n\n'
            '💡 *Примеры:*\n'
            '`/find kijin на скейте`\n'
            f'`@{bot_username} imagine dragons bones`\n'
            '`/find моя оборона`\n\n'
            '⚠️ *Обратите внимание:*\n'
            '• Скачивание занимает 10-60 секунд\n'
            '• Работаю в личке и группах\n'
            '• Треки с обложками и метаданными\n'
            '• Показываю 5 лучших результатов\n\n'
            '❤️ Приятного прослушивания!'
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f'Ошибка в help_command: {e}\n{traceback.format_exc()}')

def search_youtube(query, max_results=5):
    """Поиск видео на YouTube"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'skip_download': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'player_skip': ['webpage', 'configs']
            }
        }
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
                            'url': f"https://www.youtube.com/watch?v={entry.get('id')}",
                            'thumbnail': entry.get('thumbnail')
                        })
                return results
    except Exception as e:
        logger.error(f'Ошибка поиска на YouTube: {e}\n{traceback.format_exc()}')
    
    return []

def format_duration(seconds):
    """Форматирование длительности"""
    if not seconds:
        return '?:??'
    seconds = int(seconds)
    minutes = seconds // 60
    secs = seconds % 60
    return f'{minutes}:{secs:02d}'

def download_thumbnail(url, video_id):
    """Скачивание обложки"""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            img_path = os.path.join(TEMP_DIR, f'{video_id}_thumb.jpg')
            
            # Открываем и конвертируем в RGB (убираем альфа-канал если есть)
            img = Image.open(BytesIO(response.content))
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Сохраняем
            img.save(img_path, 'JPEG', quality=90)
            return img_path
    except Exception as e:
        logger.error(f'Ошибка скачивания обложки: {e}')
    return None

def add_metadata_and_cover(file_path, title, artist, thumbnail_path=None):
    """Добавление метаданных и обложки к аудио файлу"""
    try:
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.m4a':
            audio = MP4(file_path)
            audio['\xa9nam'] = title  # Название
            audio['\xa9ART'] = artist  # Исполнитель
            
            if thumbnail_path and os.path.exists(thumbnail_path):
                with open(thumbnail_path, 'rb') as f:
                    audio['covr'] = [MP4Cover(f.read(), imageformat=MP4Cover.FORMAT_JPEG)]
            
            audio.save()
            
        elif ext == '.webm' or ext == '.opus' or ext == '.ogg':
            audio = OggVorbis(file_path)
            audio['title'] = title
            audio['artist'] = artist
            
            if thumbnail_path and os.path.exists(thumbnail_path):
                pic = Picture()
                pic.type = 3  # Cover front
                with open(thumbnail_path, 'rb') as f:
                    pic.data = f.read()
                pic.mime = 'image/jpeg'
                audio['metadata_block_picture'] = [pic]
            
            audio.save()
        
        logger.info(f'Метаданные добавлены для {file_path}')
        return True
    except Exception as e:
        logger.error(f'Ошибка добавления метаданных: {e}\n{traceback.format_exc()}')
        return False

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка inline запросов - показывает результаты при вводе"""
    query = update.inline_query.query
    
    if not query or len(query) < 2:
        # Показываем подсказку если ничего не введено
        await update.inline_query.answer(
            [],
            button=InlineQueryResultsButton(
                text="Введите название песни для поиска",
                start_parameter="start"
            ),
            cache_time=0
        )
        return
    
    try:
        logger.info(f'Inline поиск: {query}')
        results = search_youtube(query, max_results=5)
        
        if not results:
            await update.inline_query.answer(
                [],
                button=InlineQueryResultsButton(
                    text=f"Ничего не найдено",
                    start_parameter="start"
                ),
                cache_time=10
            )
            return
        
        inline_results = []
        for track in results:
            duration = format_duration(track['duration'])
            
            # Используем video_id как result_id
            result_id = track['id']
            
            inline_results.append(
                InlineQueryResultArticle(
                    id=result_id,
                    title=track['title'],
                    description=f"⏱ {duration} | Нажмите чтобы скачать",
                    thumbnail_url=track.get('thumbnail'),
                    input_message_content=InputTextMessageContent(
                        message_text=f"⏬ *Скачиваю трек...*\n\n🎵 {track['title']}\n⏱ Подождите 10-60 секунд...",
                        parse_mode='Markdown'
                    )
                )
            )
        
        await update.inline_query.answer(
            inline_results, 
            cache_time=60,
            is_personal=True
        )
        
    except Exception as e:
        logger.error(f'Ошибка в inline_query: {e}\n{traceback.format_exc()}')
        try:
            await update.inline_query.answer(
                [],
                button=InlineQueryResultsButton(
                    text="Ошибка поиска, попробуйте позже",
                    start_parameter="start"
                ),
                cache_time=0
            )
        except:
            await update.inline_query.answer([], cache_time=0)

async def chosen_inline_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора результата из inline режима"""
    result = update.chosen_inline_result
    video_id = result.result_id
    
    try:
        logger.info(f'Выбран inline результат: {video_id}')
        
        # Получаем chat_id и message_id
        inline_message_id = result.inline_message_id
        
        # Скачиваем трек
        video_url = f'https://www.youtube.com/watch?v={video_id}'
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(TEMP_DIR, f'{video_id}.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'writethumbnail': True,
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
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            title = info.get('title', 'Unknown')
            uploader = info.get('uploader', 'Unknown')
            duration = info.get('duration', 0)
            thumbnail_url = info.get('thumbnail')
            downloaded_file = ydl.prepare_filename(info)
        
        # Скачиваем и добавляем обложку
        thumbnail_path = None
        if thumbnail_url:
            thumbnail_path = download_thumbnail(thumbnail_url, video_id)
        
        if os.path.exists(downloaded_file):
            add_metadata_and_cover(downloaded_file, title, uploader, thumbnail_path)
        
        # Обновляем сообщение
        try:
            await context.bot.edit_message_text(
                inline_message_id=inline_message_id,
                text=f'📤 *Отправляю трек...*\n\n🎵 {title}',
                parse_mode='Markdown'
            )
        except:
            pass
        
        # Отправляем аудио в тот же чат
        if os.path.exists(downloaded_file):
            thumb_data = None
            if thumbnail_path and os.path.exists(thumbnail_path):
                with open(thumbnail_path, 'rb') as thumb_file:
                    thumb_data = thumb_file.read()
            
            # Получаем ID чата из update
            # Для inline результатов нужно использовать from_user
            chat_id = result.from_user.id
            
            with open(downloaded_file, 'rb') as audio:
                sent_message = await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=audio,
                    thumbnail=thumb_data if thumb_data else None,
                    title=title,
                    performer=uploader,
                    duration=duration,
                    caption=f'🎵 *{title}*\n👤 {uploader}\n\n✅ Скачано через inline режим!',
                    parse_mode='Markdown'
                )
            
            # Обновляем inline сообщение
            try:
                await context.bot.edit_message_text(
                    inline_message_id=inline_message_id,
                    text=f'✅ *Трек отправлен!*\n\n🎵 {title}\n👤 {uploader}',
                    parse_mode='Markdown'
                )
            except:
                pass
            
            # Удаляем временные файлы
            try:
                os.remove(downloaded_file)
                if thumbnail_path and os.path.exists(thumbnail_path):
                    os.remove(thumbnail_path)
            except:
                pass
                
    except Exception as e:
        logger.error(f'Ошибка в chosen_inline_result: {e}\n{traceback.format_exc()}')
        try:
            await context.bot.edit_message_text(
                inline_message_id=inline_message_id,
                text=f'❌ *Ошибка при скачивании*\n\nПопробуйте другой трек или используйте команду /find',
                parse_mode='Markdown'
            )
        except:
            pass

async def find_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск музыки по команде /find"""
    try:
        args = context.args if context.args is not None else []
        
        if not args or len(args) == 0:
            await update.message.reply_text(
                '❌ *Ошибка!* Укажите название песни.\n\n'
                '🎯 *Пример:*\n'
                '`/find kijin на скейте`',
                parse_mode='Markdown'
            )
            return
        
        query = ' '.join(args)
        logger.info(f'Поиск музыки: {query}')
        
        search_msg = await update.message.reply_text(f'🔍 Ищу: *{query}*...', parse_mode='Markdown')
        
        try:
            results = search_youtube(query)
            
            if results and len(results) > 0:
                keyboard = []
                for i, track in enumerate(results):
                    duration = format_duration(track['duration'])
                    title = track['title']
                    if len(title) > 60:
                        title = title[:57] + '...'
                    button_text = f"{i+1}. {title} ({duration})"
                    keyboard.append([InlineKeyboardButton(
                        button_text, 
                        callback_data=f"download_{track['id']}"
                    )])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await search_msg.edit_text(
                    f'🎵 *Найдено {len(results)} треков:*\n'
                    f'Запрос: _{query}_\n\n'
                    '👇 Выберите нужный трек:',
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await search_msg.edit_text(
                    f'❌ *Ничего не найдено*\n\n'
                    f'Запрос: _{query}_\n\n'
                    '💡 Попробуйте изменить запрос или проверьте название.',
                    parse_mode='Markdown'
                )
        except Exception as search_error:
            logger.error(f'Ошибка при поиске YouTube: {search_error}\n{traceback.format_exc()}')
            await search_msg.edit_text(
                '❌ *Произошла ошибка при поиске*\n\n'
                '🔄 Попробуйте ещё раз через несколько секунд.',
                parse_mode='Markdown'
            )
    
    except Exception as e:
        logger.error(f'Критическая ошибка в find_music: {e}\n{traceback.format_exc()}')
        try:
            await update.message.reply_text(
                '❌ *Произошла критическая ошибка*\n\n'
                'Попробуйте перезапустить команду.',
                parse_mode='Markdown'
            )
        except:
            pass

async def download_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скачивание и отправка музыки"""
    query = update.callback_query
    
    try:
        await query.answer()
        
        # Проверяем тип callback (обычный или inline)
        is_inline = query.data.startswith('inline_dl_')
        video_id = query.data.replace('inline_dl_', '').replace('download_', '')
        video_url = f'https://www.youtube.com/watch?v={video_id}'
        
        logger.info(f'Скачивание трека: {video_id} (inline: {is_inline})')
        
        if is_inline:
            # Для inline режима редактируем сообщение
            await query.edit_message_text('⏬ *Скачиваю трек...*\n\n⏱ Это может занять 30-60 секунд', parse_mode='Markdown')
        else:
            await query.edit_message_text('⏬ *Скачиваю трек...*\n\n⏱ Это может занять 30-60 секунд', parse_mode='Markdown')
        
        # Скачиваем лучший доступный аудио формат
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(TEMP_DIR, f'{video_id}.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'writethumbnail': True,  # Скачиваем обложку
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                    'player_skip': ['webpage', 'configs']
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            }
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                title = info.get('title', 'Unknown')
                uploader = info.get('uploader', 'Unknown')
                duration = info.get('duration', 0)
                thumbnail_url = info.get('thumbnail')
                
                downloaded_file = ydl.prepare_filename(info)
            
            # Скачиваем обложку отдельно если нужно
            thumbnail_path = None
            if thumbnail_url:
                thumbnail_path = download_thumbnail(thumbnail_url, video_id)
            
            # Добавляем метаданные и обложку
            if os.path.exists(downloaded_file):
                add_metadata_and_cover(downloaded_file, title, uploader, thumbnail_path)
            
            await query.edit_message_text('📤 *Отправляю трек...*', parse_mode='Markdown')
            
            if os.path.exists(downloaded_file):
                # Читаем обложку для отправки
                thumb_data = None
                if thumbnail_path and os.path.exists(thumbnail_path):
                    with open(thumbnail_path, 'rb') as thumb_file:
                        thumb_data = thumb_file.read()
                
                with open(downloaded_file, 'rb') as audio:
                    await context.bot.send_audio(
                        chat_id=query.message.chat_id,
                        audio=audio,
                        thumbnail=thumb_data if thumb_data else None,
                        title=title,
                        performer=uploader,
                        duration=duration,
                        caption=f'🎵 *{title}*\n👤 {uploader}\n\n✅ Скачано успешно!',
                        parse_mode='Markdown'
                    )
                
                if is_inline:
                    await query.edit_message_text('✅ *Трек отправлен!*', parse_mode='Markdown')
                else:
                    await query.edit_message_text('✅ *Трек успешно отправлен!*', parse_mode='Markdown')
                
                # Удаляем временные файлы
                try:
                    os.remove(downloaded_file)
                    if thumbnail_path and os.path.exists(thumbnail_path):
                        os.remove(thumbnail_path)
                    logger.info(f'Файлы удалены: {downloaded_file}')
                except Exception as e:
                    logger.error(f'Ошибка при удалении файлов: {e}')
            else:
                await query.edit_message_text(
                    '❌ *Ошибка*\n\n'
                    'Файл не найден после скачивания.\n'
                    'Попробуйте другой трек.',
                    parse_mode='Markdown'
                )
        
        except Exception as download_error:
            logger.error(f'Ошибка при скачивании: {download_error}\n{traceback.format_exc()}')
            await query.edit_message_text(
                '❌ *Произошла ошибка при скачивании*\n\n'
                '💡 Возможные причины:\n'
                '• Видео недоступно\n'
                '• Проблемы с сервером\n'
                '• Слишком длинный трек\n\n'
                '🔄 Попробуйте другой трек.',
                parse_mode='Markdown'
            )
            
            # Очистка при ошибке
            try:
                for file in os.listdir(TEMP_DIR):
                    if file.startswith(video_id):
                        os.remove(os.path.join(TEMP_DIR, file))
            except:
                pass
    
    except Exception as e:
        logger.error(f'Критическая ошибка в download_and_send: {e}\n{traceback.format_exc()}')
        try:
            await query.answer('Произошла ошибка')
        except:
            pass

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех ошибок"""
    logger.error(f'Обработка ошибки: {context.error}\n{traceback.format_exc()}')
    
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                '❌ Произошла ошибка. Бот продолжает работу.',
                parse_mode='Markdown'
            )
    except:
        pass

def main():
    """Запуск бота"""
    try:
        if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
            logger.error('❌ Ошибка: не установлен BOT_TOKEN!')
            logger.error('Установите переменную окружения BOT_TOKEN или измените её в коде')
            return
        
        logger.info('🚀 Инициализация бота...')
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Регистрируем обработчики команд
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("find", find_music))
        
        # Обработчик inline запросов
        application.add_handler(InlineQueryHandler(inline_query))
        
        # Обработчик выбора inline результата
        application.add_handler(ChosenInlineResultHandler(chosen_inline_result))
        
        # Обработчик добавления бота в группу
        application.add_handler(MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS,
            new_chat_member
        ))
        
        # Обработчик нажатий на кнопки
        application.add_handler(CallbackQueryHandler(download_and_send))
        
        # Обработчик ошибок
        application.add_error_handler(error_handler)
        
        # Запускаем бота
        logger.info('✅ Бот успешно запущен!')
        logger.info('🎵 Ожидаю команды /find и inline запросы...')
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    
    except Exception as e:
        logger.error(f'Критическая ошибка при запуске: {e}\n{traceback.format_exc()}')
        raise

if __name__ == '__main__':
    main()
