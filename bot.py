# bot.py
import logging
import os
import traceback
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
    try:
        welcome_text = (
            '🎵 *Привет! Я Music Bot!*\n\n'
            '✨ Я помогу вам находить и скачивать музыку с YouTube.\n\n'
            '📋 *Доступные команды:*\n'
            '/find <название песни> - Найти и скачать трек\n'
            '/help - Помощь и инструкция\n'
            '/start - Показать это сообщение\n\n'
            '🎯 *Пример использования:*\n'
            '`/find kijin на скейте`\n'
            '`/find coldplay yellow`\n\n'
            '💡 Просто напишите команду /find и название песни!'
        )
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f'Ошибка в start: {e}\n{traceback.format_exc()}')

async def new_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие при добавлении бота в группу"""
    try:
        for member in update.message.new_chat_members:
            if member.id == context.bot.id:
                welcome_text = (
                    '👋 *Привет всем! Спасибо, что добавили меня в чат!*\n\n'
                    '🎵 Я Music Bot - помогу находить и скачивать музыку.\n\n'
                    '📋 *Команды для работы со мной:*\n'
                    '🔍 `/find <название>` - Найти трек\n'
                    '❓ `/help` - Подробная инструкция\n\n'
                    '🎯 *Пример:*\n'
                    '`/find kijin на скейте`\n\n'
                    '✅ Готов к работе! Пишите /find и название песни!'
                )
                await update.message.reply_text(welcome_text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f'Ошибка в new_chat_member: {e}\n{traceback.format_exc()}')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справка по командам"""
    try:
        help_text = (
            '📖 *Инструкция по использованию Music Bot*\n\n'
            '🔍 *Как искать музыку:*\n'
            '1. Напишите `/find` и название песни\n'
            '2. Я найду несколько вариантов\n'
            '3. Выберите нужный трек кнопкой\n'
            '4. Дождитесь скачивания\n'
            '5. Получите полную песню в MP3!\n\n'
            '📋 *Команды:*\n'
            '`/find <название>` - Найти трек\n'
            '`/help` - Эта справка\n'
            '`/start` - Приветствие\n\n'
            '💡 *Примеры запросов:*\n'
            '`/find kijin на скейте`\n'
            '`/find imagine dragons bones`\n'
            '`/find моя оборона`\n\n'
            '⚠️ *Обратите внимание:*\n'
            '• Скачивание занимает 10-60 секунд\n'
            '• Работаю в личке и группах\n'
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
                            'url': f"https://www.youtube.com/watch?v={entry.get('id')}"
                        })
                return results
    except Exception as e:
        logger.error(f'Ошибка поиска на YouTube: {e}\n{traceback.format_exc()}')
    
    return []

def format_duration(seconds):
    """Форматирование длительности"""
    if not seconds:
        return '?:??'
    seconds = int(seconds)  # Преобразуем в целое число
    minutes = seconds // 60
    secs = seconds % 60
    return f'{minutes}:{secs:02d}'

async def find_music(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск музыки по команде /find"""
    try:
        # Безопасная проверка аргументов
        args = context.args if context.args is not None else []
        
        if not args or len(args) == 0:
            await update.message.reply_text(
                '❌ *Ошибка!* Укажите название песни.\n\n'
                '🎯 *Пример:*\n'
                '`/find kijin на скейте`',
                parse_mode='Markdown'
            )
            return
        
        # Собираем запрос из аргументов
        query = ' '.join(args)
        logger.info(f'Поиск музыки: {query}')
        
        search_msg = await update.message.reply_text(f'🔍 Ищу: *{query}*...', parse_mode='Markdown')
        
        try:
            results = search_youtube(query)
            
            if results and len(results) > 0:
                # Создаём кнопки для выбора
                keyboard = []
                for i, track in enumerate(results):
                    duration = format_duration(track['duration'])
                    # Сокращаем название для кнопки
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
        
        video_id = query.data.replace('download_', '')
        video_url = f'https://www.youtube.com/watch?v={video_id}'
        
        logger.info(f'Скачивание трека: {video_id}')
        
        await query.edit_message_text('⏬ *Скачиваю трек...*\n\n⏱ Это может занять 30-60 секунд', parse_mode='Markdown')
        
        # Скачиваем аудио БЕЗ конвертации (быстрее и не требует FFmpeg)
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio',
            'outtmpl': os.path.join(TEMP_DIR, f'{video_id}.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
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
                
                # Получаем реальное имя скачанного файла
                downloaded_file = ydl.prepare_filename(info)
            
            await query.edit_message_text('📤 *Отправляю трек...*', parse_mode='Markdown')
            
            # Проверяем что файл существует
            if os.path.exists(downloaded_file):
                with open(downloaded_file, 'rb') as audio:
                    await context.bot.send_audio(
                        chat_id=query.message.chat_id,
                        audio=audio,
                        title=title,
                        performer=uploader,
                        duration=duration,
                        caption=f'🎵 *{title}*\n\n✅ Скачано успешно!',
                        parse_mode='Markdown'
                    )
                
                await query.edit_message_text('✅ *Трек успешно отправлен!*', parse_mode='Markdown')
                
                # Удаляем временный файл
                try:
                    os.remove(downloaded_file)
                    logger.info(f'Файл удалён: {downloaded_file}')
                except Exception as e:
                    logger.error(f'Ошибка при удалении файла: {e}')
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
            
            # Очистка при ошибке - удаляем все файлы с этим video_id
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
        logger.info('🎵 Ожидаю команды /find...')
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    
    except Exception as e:
        logger.error(f'Критическая ошибка при запуске: {e}\n{traceback.format_exc()}')
        raise

if __name__ == '__main__':
    main()
