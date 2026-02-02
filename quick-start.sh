#!/bin/bash

echo "🎵 Telegram Music Bot - Быстрый запуск"
echo "====================================="

# Проверка .env файла
if [ ! -f .env ]; then
    echo ""
    echo "⚠️  Файл .env не найден!"
    echo ""
    echo "Создаю .env файл..."
    cp .env.example .env
    echo ""
    echo "📝 Отредактируй файл .env и укажи свой BOT_TOKEN"
    echo "   Получи токен у @BotFather в Telegram"
    echo ""
    echo "После этого запусти скрипт снова:"
    echo "   ./quick-start.sh"
    exit 1
fi

# Загрузка переменных
export $(cat .env | grep -v '^#' | xargs)

# Проверка токена
if [ -z "$BOT_TOKEN" ] || [ "$BOT_TOKEN" = "your_bot_token_here" ]; then
    echo "❌ Токен не установлен в .env файле!"
    echo "   Отредактируй .env и укажи токен от @BotFather"
    exit 1
fi

# Выбор метода запуска
echo ""
echo "Выберите метод запуска:"
echo "1) Docker (рекомендуется)"
echo "2) Прямой запуск Python"
echo ""
read -p "Ваш выбор (1 или 2): " choice

case $choice in
    1)
        echo ""
        echo "🐳 Запуск через Docker..."
        
        # Проверка Docker
        if ! command -v docker &> /dev/null; then
            echo "❌ Docker не установлен!"
            echo "   Установи: https://docs.docker.com/get-docker/"
            exit 1
        fi
        
        if ! command -v docker-compose &> /dev/null; then
            echo "❌ Docker Compose не установлен!"
            echo "   Установи: https://docs.docker.com/compose/install/"
            exit 1
        fi
        
        # Запуск
        docker-compose up -d
        
        echo ""
        echo "✅ Бот запущен в Docker!"
        echo ""
        echo "📋 Полезные команды:"
        echo "   docker-compose logs -f     # Смотреть логи"
        echo "   docker-compose ps          # Статус"
        echo "   docker-compose restart     # Перезапуск"
        echo "   docker-compose down        # Остановить"
        ;;
        
    2)
        echo ""
        echo "🐍 Запуск через Python..."
        
        # Проверка Python
        if ! command -v python3 &> /dev/null; then
            echo "❌ Python 3 не установлен!"
            exit 1
        fi
        
        # Проверка FFmpeg
        if ! command -v ffmpeg &> /dev/null; then
            echo "⚠️  FFmpeg не найден! Установи для конвертации аудио:"
            echo "   Ubuntu/Debian: sudo apt-get install ffmpeg"
            echo "   macOS: brew install ffmpeg"
            echo "   Windows: https://ffmpeg.org/download.html"
            read -p "Продолжить без FFmpeg? (y/n): " cont
            if [ "$cont" != "y" ]; then
                exit 1
            fi
        fi
        
        # Установка зависимостей
        if [ ! -d "venv" ]; then
            echo "📦 Создаю виртуальное окружение..."
            python3 -m venv venv
        fi
        
        echo "📦 Устанавливаю зависимости..."
        source venv/bin/activate
        pip install -r requirements.txt
        
        # Запуск
        echo ""
        echo "🚀 Запускаю бота..."
        python bot.py
        ;;
        
    *)
        echo "❌ Неверный выбор!"
        exit 1
        ;;
esac
