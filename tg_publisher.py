import telegram
from environs import Env



def publish_post_to_tg(text: str, photo = None):
	try:
		env = Env()
		env.read_env()
		chat_id = env.str('CHAT_ID')
		bot = telegram.Bot(token=env.str('TG_BOT_TOKEN'))
		if photo:
			result = bot.send_photo(chat_id=chat_id, photo=photo, caption=text)
			return result['message_id']
		if not photo:
			result = bot.send_message(chat_id=chat_id, text=text)
			return result['message_id']
	except Exception as er:
		pass


def delete_post_from_tg(post_id):
	try:
		env = Env()
		env.read_env()
		chat_id = env.str('CHAT_ID')
		bot = telegram.Bot(token=env.str('TG_BOT_TOKEN'))

		result = bot.delete_message(chat_id=chat_id, message_id=post_id)
		return result
	except Exception as er:
		pass
		

	# доделать отработку, если пользователь передает только текст или только фото