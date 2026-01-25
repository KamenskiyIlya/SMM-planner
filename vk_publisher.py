import os
import requests
from environs import Env

from utils.exceptions import ApiError, AuthError, NetworkError


env = Env()
env.read_env()

VK_API_TOKEN = env.str('VK_API_TOKEN')  # user access token (photos, wall, groups, offline)
VK_GROUP_ID = int(env.str('VK_GROUP_ID'))  # без минуса
VK_API_VERSION = '5.199'


def _vk_call(method, params):
    url = f'https://api.vk.com/method/{method}'
    params = {**params, 'access_token': VK_API_TOKEN, 'v': VK_API_VERSION}

    try:
        response = requests.post(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        raise NetworkError('VK', str(e))
    except ValueError as e:
        raise ApiError('VK', f'Bad JSON from VK: {e}')

    if 'error' in data:
        err = data['error']
        code = str(err.get('error_code'))
        msg = err.get('error_msg', 'VK error')
        if code == '5':
            raise AuthError('VK', msg, code=code)
        raise ApiError('VK', msg, code=code)

    return data.get('response')


def upload_photo_for_wall(image_source):
    # 1) Получаем upload_url
    response = _vk_call('photos.getWallUploadServer', {'group_id': VK_GROUP_ID})
    upload_url = response['upload_url']

    # 2) Загружаем файл
    try:
        if hasattr(image_source, 'read'):
            image_source.seek(0)
            files = {'photo': image_source}
        elif isinstance(image_source, str):
            if image_source.startswith('http'):
                image_bytes = requests.get(image_source, timeout=30).content
                files = {'photo': image_bytes}
            else:
                files = {'photo': open(image_source, 'rb')}
        else:
            raise TypeError('Неподдерживаемый тип image_source')

        response = requests.post(upload_url, files=files, timeout=60)
        response.raise_for_status()
        upload_response = response.json()
    except requests.exceptions.RequestException as e:
        raise NetworkError('VK', str(e))
    except ValueError as e:
        raise ApiError('VK', f'Получен некорректный JSON: {e}')

    # 3) Сохраняем фото
    saved = _vk_call(
        'photos.saveWallPhoto',
        {
            'group_id': VK_GROUP_ID,
            'photo': upload_response['photo'],
            'server': upload_response['server'],
            'hash': upload_response['hash'],
        },
    )

    photo = saved[0]
    return f"photo{photo['owner_id']}_{photo['id']}"


# gif грузим как документ для стены
def upload_gif_for_wall(image_source):
    response = _vk_call('docs.getWallUploadServer', {'group_id': VK_GROUP_ID})
    upload_url = response['upload_url']

    try:
        if hasattr(image_source, 'read'):
            image_source.seek(0)
            files = {'file': image_source}
        elif isinstance(image_source, str):
            if image_source.startswith('http'):
                image_bytes = requests.get(image_source, timeout=30).content
                files = {'file': image_bytes}
            else:
                files = {'file': open(image_source, 'rb')}
        else:
            raise TypeError('Неподдерживаемый тип image_source')

        response = requests.post(upload_url, files=files, timeout=60)
        response.raise_for_status()
        upload_response = response.json()
    except requests.exceptions.RequestException as e:
        raise NetworkError('VK', str(e))
    except ValueError as e:
        raise ApiError('VK', f'Bad JSON from upload: {e}')

    saved = _vk_call('docs.save', {'file': upload_response['file']})
    doc = saved['doc']

    access_key = doc.get('access_key')
    if access_key:
        return f"doc{doc['owner_id']}_{doc['id']}_{access_key}"
    return f"doc{doc['owner_id']}_{doc['id']}"


def publish_post_to_vk(post_text, image_source=None, image_ext=None):
    if not post_text and not image_source:
        raise ApiError('VK', 'Нет контента для публикации')

    if not image_ext and hasattr(image_source, 'name'):
        image_ext = os.path.splitext(str(image_source.name))[1].lower()

    attachments = []
    if image_source:
        # если .gif — грузим как doc, иначе как photo
        if (image_ext or '').lower() == '.gif':
            attachments.append(upload_gif_for_wall(image_source))
        else:
            attachments.append(upload_photo_for_wall(image_source))

    response = _vk_call(
        'wall.post',
        {
            'owner_id': -VK_GROUP_ID,
            'from_group': 1,
            'message': post_text or '',
            'attachments': ','.join(attachments) if attachments else None,
        },
    )

    post_id = response.get('post_id') if isinstance(response, dict) else None
    if not post_id:
        raise ApiError('VK', f'Неожиданный ответ VK: {response}')
    return post_id


def delete_post_from_vk(post_id):
    response = _vk_call('wall.delete', {'owner_id': -VK_GROUP_ID, 'post_id': post_id})
    return response == 1
