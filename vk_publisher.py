import requests
import re
from environs import Env


def publish_post_vk(api_key, id_channel, text, urls_img):
    params = {
        'owner_id': f'-{id_channel}',
        'from_group': '1',
        'message': text,
        'access_token': api_key,
        'v': '5.199',
    }
    attachments = None
    if urls_img[0]:
        match = re.search(r'photo-(\d+_\d+)', urls_img[0])
        if match:
            attachments = f'photo-{match.group(1)}'
            params['attachments'] = attachments

    response = requests.post('https://api.vk.com/method/wall.post', params=params)
    response.raise_for_status()


def main():
    env = Env()
    env.read_env()
    api_key = env.str('VK_API_KEY')      # ваш личный токен доступа VK API
    channel_id = env.str('CHANNEL_ID')       # ID сообщества, куда публикуем пост (без минуса!)
    post_text = 'Привет, друзья!'    # текст поста
    image_urls = ['photo-123456789_456789012']  # URL или ID прикрепляемой фотографии

    # Вызов функции публикации поста
    try:
        publish_post_vk(api_key, channel_id, text=post_text, urls_img=image_urls)
        print("Пост опубликован успешно!")
    except requests.exceptions.HTTPError as e:
        print(f"Возникла ошибка при публикации поста: {e.response.text}")
    except Exception as ex:
        print(f"Неожиданная ошибка: {ex}")


if __name__ == "__main__":
    main()