import telegram
from environs import Env


def upload_post(text: str, photo, chat_id, bot):
	try:
		bot.send_photo(chat_id=chat_id, photo=photo, caption=text)
		return True
	except:
		return False

	# доделать отработку, если пользователь передает только текст или только фото