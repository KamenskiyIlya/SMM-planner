import os
import requests
import telegram
from environs import Env
from utils.exceptions import ApiError


def _get_bot():
    env = Env()
    env.read_env()
    chat_id = env.str('CHAT_ID')
    bot = telegram.Bot(token=env.str('TG_BOT_TOKEN'))
    return bot, chat_id


def _is_url(value):
    return isinstance(value, str) and value.startswith(('http://', 'https://'))


def publish_post_to_tg(post_text, image_source, image_ext=None):
    try:
        bot, chat_id = _get_bot()
        # --- если нет картинки ---
        if not image_source:
            msg = bot.send_message(chat_id=chat_id, text=post_text)
            return msg.message_id

        # --- определить расширение ---
        if not image_ext:
            if hasattr(image_source, 'name'):
                image_ext = os.path.splitext(image_source.name)[1].lower()
            elif isinstance(image_source, str):
                image_ext = os.path.splitext(image_source)[1].lower()

        # --- GIF ---
        if image_ext == '.gif':
            if _is_url(image_source):
                msg = bot.send_document(
                    chat_id=chat_id,
                    document=image_source,
                    caption=post_text
                )
            else:
                with open(image_source, 'rb') as file:
                    msg = bot.send_document(
                        chat_id=chat_id,
                        document=file,
                        caption=post_text
                    )
            return msg.message_id

        # --- обычное фото ---
        if _is_url(image_source):
            msg = bot.send_photo(
                chat_id=chat_id,
                photo=image_source,
                caption=post_text
            )
        else:
            with open(image_source, 'rb') as file:
                msg = bot.send_photo(
                    chat_id=chat_id,
                    photo=file,
                    caption=post_text
                )

        return msg.message_id

    except telegram.error.TelegramError as e:
        raise ApiError('TG', str(e))

    except requests.exceptions.RequestException as e:
        raise ApiError('TG', f'Network error: {e}')


def delete_post_from_tg(post_id) -> bool:
    bot, chat_id = _get_bot()
    try:
        return bool(bot.delete_message(chat_id=chat_id, message_id=post_id))
    except telegram.error.TelegramError as e:
        raise ApiError('TG', str(e))
