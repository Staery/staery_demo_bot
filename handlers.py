from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, Filters
import logging

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

logger = logging.getLogger(__name__)


# /start command handler
def start(update: Update, context: CallbackContext) -> None:
    reply_keyboard = [['/help', '/status']]
    update.message.reply_text(
        'Привет! Я бот, который может показывать статус и помощь.\n'
        'Нажми /help, чтобы узнать, что я могу',
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))


# /help command handler
def help_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        'Я умею отвечать на команды:\n'
        '/start - запустить бота\n'
        '/help - показать помощь\n'
        '/status - показать статус')


# /status command handler
def status_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Все системы работают нормально!')


# New chat members handler
def new_chat_members(update: Update, context: CallbackContext) -> None:
    for member in update.message.new_chat_members:
        update.message.reply_text(f'Добро пожаловать, {member.first_name}!')


# Echo message handler
def echo_message(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(update.message.text)


# Error handler
def error(update: Update, context: CallbackContext) -> None:
    logger.warning('Update "%s" caused error "%s"', update, context.error)
    update.message.reply_text('Произошла ошибка.')


# Command unknown handler
def unknown_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Неизвестная команда')


# Help button handler
def help_button(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        'Я умею отвечать на команды:\n'
        '/start - запустить бота\n'
        '/help - показать помощь\n'
        '/status - показать статус',
        reply_markup=ReplyKeyboardRemove()
    )
