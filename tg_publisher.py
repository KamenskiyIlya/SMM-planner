import telegram
from environs import Env


def upload_post(text: str, photo, chat_id, bot):
	bot.send_photo(chat_id=chat_id, photo=photo, caption=text)


def main():
	env = Env()
	env.read_env()
	chat_id = env.str('CHAT_ID')
	bot = telegram.Bot(token=env.str('TG_BOT_TOKEN'))

	# ссылка на фото для примера, позже настроим постинг в нужном формате
	upload_post(
		'Привет!',
		'https://www.litres.ru/journal/c/covers/212185/logo/212185_logo.jpg',
		chat_id,
		bot
	)


if __name__ == '__main__':
	main()
