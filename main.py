import json
import logging
import os
import argparse
from telegram.ext import Updater, ConversationHandler
from telegram import Update, ParseMode, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import CallbackContext
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler, Filters
import pandas as pd

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

parser = argparse.ArgumentParser()
parser.add_argument("--config", "-c", required=True)
args = parser.parse_args()

AUTH, FINISH_AUTH, COMPLETE, ERROR = range(4)


def start(update: Update, context: CallbackContext) -> int:
	db = context.bot_data["participants"]
	if str(update.message.from_user.id) not in db.index:
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
	contact_phone_number = int(update.message.contact.phone_number)

	if user_id != contact_user_id:
		context.bot.send_message(chat_id=update.effective_chat.id,
		                         text="Ошибка: user_id контакта не совпадает с user_id отправителя.",
		                         reply_markup=ReplyKeyboardRemove())
		error_state(update, context)
		return ERROR

	db = context.bot_data["db"]
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
	db = context.bot_data["db"]
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
		user_data = [update.message.from_user.username,
		             context.bot_data["db"].loc[phone_number, "name"],
		             update.message.chat_id,
		             phone_number]
		db = context.bot_data["participants"]
		db.loc[update.message.from_user.id] = user_data
		db.to_csv(context.bot_data["config"]["participants_path"])

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
	context.bot.send_message(chat_id=update.effective_chat.id, text="Список доступных комманд:\n\\help\n\\start.")
	return COMPLETE


def error_state(update: Update, context: CallbackContext) -> int:
	context.bot.send_message(chat_id=update.effective_chat.id,
	                         text="Отчёт об ошибке будет отправлени организатору игры."
	                              "Проблему исправят в ближайшее время.")
	return ERROR


def restart(update: Update, context: CallbackContext):
	context.bot_data["participants"].drop(index=update.message.from_user.id, inplace=True)
	context.bot_data["participants"].to_csv(context.bot_data["config"]["participants_path"])
	return start(update, context)


def main():
	with open(args.config) as input_stream:
		config = json.load(input_stream)
	with open(config["token_path"], "r") as input_stream:
		TOKEN = input_stream.readline().strip()

	updater = Updater(token=TOKEN)
	dispatcher = updater.dispatcher
	dispatcher.bot_data["config"] = config
	dispatcher.bot_data["db"] = pd.read_csv(config["db_path"], index_col=1, header=0,
	                                        dtype={"name": str, "phone": int})
	if os.path.exists(config["participants_path"]):
		dispatcher.bot_data["participants"] = pd.read_csv(config["participants_path"],
		                                                  index_col=0, header=0)
	else:
		dispatcher.bot_data["participants"] = pd.DataFrame(columns=["user_id", "username", "name",
		                                                   "chat_id", "phone"]).set_index("user_id")

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


if __name__ == "__main__":
	main()
