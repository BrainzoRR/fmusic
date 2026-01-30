#!/bin/bash

echo "🚀 Установка Telegram Music Bot"
echo "================================"

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  Запустите скрипт с правами root (sudo ./start.sh)"
    exit 1
fi

# Обновление системы
echo "📦 Обновление системных пакетов..."
apt-get update

# Установка зависимостей
echo "📦 Установка Python..."
apt-get install -y python3 python3-pip

# Установка Python библиотек
echo "📦 Установка Python библиотек..."
pip3 install -r requirements.txt

# Получение токена
if [ -z "$BOT_TOKEN" ]; then
    if [ -f ".env" ]; then
        echo "📄 Загрузка токена из .env файла..."
        export $(cat .env | xargs)
    else
        echo ""
        echo "⚠️  ВНИМАНИЕ! Не установлена переменная BOT_TOKEN"
        echo "Введите токен вашего бота (получите у @BotFather):"
        read -r BOT_TOKEN
        echo "BOT_TOKEN=$BOT_TOKEN" > .env
        export BOT_TOKEN
    fi
fi

# Проверка наличия токена
if [ -z "$BOT_TOKEN" ] || [ "$BOT_TOKEN" = "your_bot_token_here" ]; then
    echo "❌ Ошибка: токен не установлен!"
    echo "Отредактируйте файл .env и вставьте токен от @BotFather"
    exit 1
fi

# Создание systemd service
echo "📝 Создание systemd service..."
CURRENT_DIR=$(pwd)

cat > /etc/systemd/system/music-bot.service <<EOF
[Unit]
Description=Telegram Music Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$CURRENT_DIR
Environment="BOT_TOKEN=$BOT_TOKEN"
ExecStart=/usr/bin/python3 $CURRENT_DIR/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Перезагрузка systemd
echo "🔄 Перезагрузка systemd..."
systemctl daemon-reload

# Включение автозапуска
echo "✅ Включение автозапуска..."
systemctl enable music-bot.service

# Запуск бота
echo "🚀 Запуск бота..."
systemctl start music-bot.service

# Проверка статуса
sleep 2
echo ""
echo "================================"
echo "📊 Статус бота:"
systemctl status music-bot.service --no-pager

echo ""
echo "================================"
echo "✅ Установка завершена!"
echo ""
echo "📋 Полезные команды:"
echo "  systemctl status music-bot   - Проверить статус"
echo "  systemctl stop music-bot     - Остановить бота"
echo "  systemctl start music-bot    - Запустить бота"
echo "  systemctl restart music-bot  - Перезапустить бота"
echo "  journalctl -u music-bot -f   - Смотреть логи в реальном времени"
echo ""
echo "🎵 Бот запущен и работает в фоне!"
