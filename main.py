import logging
import os

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from dotenv import load_dotenv
import config
import handlers


load_dotenv()

# Получаем токен бота из переменной окружения
TELEGRAM_BOT_TOKEN = config.TELEGRAM_BOT_TOKEN

# Настраиваем логгер
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Создаем экземпляр Updater и передаем ему токен бота
updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)

# Получаем экземпляр диспетчера
dispatcher = updater.dispatcher

# Регистрируем обработчик команды /start
start_handler = CommandHandler('start', handlers.start)
dispatcher.add_handler(start_handler)

# Регистрируем обработчик команды /help
help_handler = CommandHandler('help', handlers.help)
dispatcher.add_handler(help_handler)

# Регистрируем обработчик команды /random_image
random_image_handler = CommandHandler('random_image', handlers.random_image)
dispatcher.add_handler(random_image_handler)

# Регистрируем обработчик события добавления новых участников в группу или канал
new_chat_members_handler = MessageHandler(Filters.status_update.new_chat_members, handlers.new_chat_members)
dispatcher.add_handler(new_chat_members_handler)

# Запускаем бота
updater.start_polling()
import logging
import os

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from dotenv import load_dotenv
import config
import handlers


load_dotenv()

# Получаем токен бота из переменной окружения
TELEGRAM_BOT_TOKEN = config.TELEGRAM_BOT_TOKEN

# Настраиваем логгер
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Создаем экземпляр Updater и передаем ему токен бота
updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)

# Получаем экземпляр диспетчера
dispatcher = updater.dispatcher

# Регистрируем обработчик команды /start
start_handler = CommandHandler('start', handlers.start)
dispatcher.add_handler(start_handler)

# Регистрируем обработчик команды /help
help_handler = CommandHandler('help', handlers.help)
dispatcher.add_handler(help_handler)

# Регистрируем обработчик команды /random_image
random_image_handler = CommandHandler('random_image', handlers.random_image)
dispatcher.add_handler(random_image_handler)

# Регистрируем обработчик события добавления новых участников в группу или канал
new_chat_members_handler = MessageHandler(Filters.status_update.new_chat_members, handlers.new_chat_members)
dispatcher.add_handler(new_chat_members_handler)

# Запускаем бота
updater.start_polling()
