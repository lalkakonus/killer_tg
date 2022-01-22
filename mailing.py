import logging
import pandas as pd
from time import sleep
from telegram import Bot, TelegramError

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


def process():
	participants = pd.read_csv("data/test_participants.csv")
	participants = participants.sample(frac=1).reset_index(drop=True)

	# Form data in suitable format
	participants["victim_username"] = participants["username"][1:].to_list() + [participants["username"][0], ]
	participants["victim_name"] = participants["name"][1:].to_list() + [participants["name"][0], ]
	participants["victim_chat_id"] = participants["chat_id"][1:].to_list() + [participants["chat_id"][0], ]
	participants.to_csv("data/table.csv", index=False)


def get_text(row):
	string = ""
	victim_username = row["victim_username"]
	victim_name = row["victim_name"]
	string += "Привет, твоя жертва @{} ({})".format(victim_username, victim_name)
	string += "\n\nГде она живёт? Я не скажу, это тебе надо выяснить самостоятельно. "
	string += "По остальным возникшим вопросам обращайся к @lalkakonus (Сергею Кононову)."
	return string


def mailing(token):
	bot = Bot(token=token)
	data = pd.read_csv("data/table.csv")
	for key, row in data.iterrows():
		try:
			bot.send_message(row["chat_id"], text=get_text(row))
		except TelegramError as error:
			logging.error("chat_id [{}] ERROR:".format(row["username"]))
			logging.error("\tError text: {}".format(error.message))
		logging.debug("chat_id [{}] OK".format(row["username"]))
		sleep(0.5)


def main(token):
	mailing(token)
	# process()


if __name__ == "__main__":
	with open("data/token", "r") as input_stream:
		TOKEN = input_stream.readline().strip()
	main(TOKEN)
