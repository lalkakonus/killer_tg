import logging
from telegram.ext import Updater, ConversationHandler
from telegram import Update, ForceReply, ParseMode, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import CallbackContext
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler, Filters
import pandas as pd

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

AUTH, FINISH_AUTH, COMPLETE, ERROR = range(4)

# data = [
# 		["79629498099", "Сергей Кононов", None, None],
# 		["79858948307", "Маша Алексеева", None, None],
# 		["79166835422", "Степан Зимов", None, None],
# ]
# db = pd.DataFrame(data, columns=["phone", "name", "tg_account", "tg_user_id"]).set_index("phone")
db = pd.read_csv("data/data.csv", sep="\t", index_col=0, header=0, dtype=str)
db.set_index(db.index.astype(str), inplace=True)


def start(update: Update, context: CallbackContext) -> int:
	if str(update.message.from_user.id) not in db["tg_user_id"].values:
		request_phone_number(update, context)
		return AUTH
	else:
		context.bot.send_message(chat_id=update.effective_chat.id,
		                         text="Ты уже зарегестрирован в игру.")
		return COMPLETE


def request_phone_number(update: Update, context: CallbackContext) -> int:
	update.message.reply_text(
		"Привет! Отправь, пожалуйста, свои контактные данные для идентефикации.",
		reply_markup=ReplyKeyboardMarkup(
			[[KeyboardButton("Отправить мой телефонный номер", request_contact=True), ], ],
			one_time_keyboard=True,
			resize_keyboard=True
		),
	)
	return AUTH


def auth(update: Update, context: CallbackContext) -> int:
	user_id = update.message.from_user.id
	contact_user_id = update.message.contact.user_id
	contact_phone_number = update.message.contact.phone_number

	if user_id != contact_user_id:
		context.bot.send_message(chat_id=update.effective_chat.id,
		                         text="Ошибка: user_id контакта не совпадает с user_id отправителя.",
		                         reply_markup=ReplyKeyboardRemove())
		error_state(update, context)
		return ERROR

	if contact_phone_number not in db.index:
		context.bot.send_message(chat_id=update.effective_chat.id,
		                         text="Ошибка: номер телефона отсутсвует в базе данных.",
		                         reply_markup=ReplyKeyboardRemove())
		error_state(update, context)
		return ERROR

	context.user_data["phone_number"] = contact_phone_number
	request_name_approve(update, context)
	return FINISH_AUTH


def request_name_approve(update: Update, context: CallbackContext) -> int:
	name = db.loc[context.user_data["phone_number"]]["name"]
	update.message.reply_text(
		"Тебя зовут {name}, верно?".format(name=name),
		reply_markup=ReplyKeyboardMarkup(
			[["Да", "Нет"], ],
			one_time_keyboard=True,
			resize_keyboard=True
		),
	)
	return FINISH_AUTH


def finish_auth(update: Update, context: CallbackContext) -> int:
	if update.message.text == "Да":
		phone_number = context.user_data["phone_number"]
		db.loc[phone_number]["tg_account"] = update.message.from_user.username
		db.loc[phone_number]["tg_user_id"] = update.message.from_user.id
		db.to_csv("data.csv", sep="\t")
		context.bot.send_message(chat_id=update.effective_chat.id, text="Отлично, ты записан в игру.")
		return COMPLETE
	elif update.message.text == "Нет":
		context.bot.send_message(chat_id=update.effective_chat.id,
		                         text="Отчёт об ошибке будет отправлени организатору игры."
		                              "Проблему исправят в ближайшее время.",
		                         reply_markup=ReplyKeyboardRemove())
		return ERROR
	else:
		raise ValueError("Unexpected argument")


def print_rules(update: Update, context: CallbackContext) -> int:
	context.bot.send_message(chat_id=update.effective_chat.id,
	                         parse_mode=ParseMode.MARKDOWN_V2,
	                         text="__Правила проведения игры__")
	return COMPLETE


def help_command(update: Update, context: CallbackContext) -> int:
	context.bot.send_message(chat_id=update.effective_chat.id, text="Список доступных комманд:\n\help\n\start.")
	return COMPLETE


def error_state(update: Update, context: CallbackContext) -> int:
	context.bot.send_message(chat_id=update.effective_chat.id,
	                         text="Отчёт об ошибке будет отправлени организатору игры."
	                              "Проблему исправят в ближайшее время.")
	return ERROR


def restart(update: Update, context: CallbackContext):
	db.loc[db["tg_user_id"] == str(update.message.from_user.id), "tg_account"] = None
	db.loc[db["tg_user_id"] == str(update.message.from_user.id), "tg_user_id"] = None
	db.to_csv("data.csv", sep="\t")
	return start(update, context)


def main():
	TOKEN = ""
	updater = Updater(token=TOKEN)
	dispatcher = updater.dispatcher

	conv_handler = ConversationHandler(
		entry_points=[CommandHandler('start', start)],
		states={
			AUTH: [
				MessageHandler(Filters.contact, auth),
				MessageHandler(~Filters.contact, request_phone_number), ],
			FINISH_AUTH: [
				MessageHandler(Filters.regex('[Да|Нет]'), finish_auth),
				MessageHandler(~Filters.regex('[Да|Нет]'), request_name_approve), ],
			COMPLETE: [
				CommandHandler('rules', print_rules),
				CommandHandler('help', help_command),
				CommandHandler('restart', restart), ],
			ERROR: [
				CommandHandler('restart', restart),
				MessageHandler(Filters.text, error_state), ]
		},
		fallbacks=[CommandHandler('restart', restart)],
	)

	dispatcher.add_handler(conv_handler)

	updater.start_polling()
	updater.idle()

main()