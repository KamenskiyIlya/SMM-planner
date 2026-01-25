import io
import json
import os
import requests
from environs import Env

from utils.exceptions import ApiError, NetworkError
from utils.ok_md5hex import make_sig


env = Env()
env.read_env()

OK_APP_PUBLIC_KEY = env.str('OK_APP_PUBLIC_KEY')
OK_SESSION_SECRET_KEY = env.str('OK_SESSION_SECRET_KEY')
OK_ACCESS_TOKEN = env.str('OK_ACCESS_TOKEN')
OK_GROUP_ID = env.str('OK_GROUP_ID')

OK_API_URL = 'https://api.ok.ru/fb.do'


def ok_api_response(method, extra_params):
    """Вызов OK API"""
    params = {
        'method': method,
        'application_key': OK_APP_PUBLIC_KEY,
        'access_token': OK_ACCESS_TOKEN,
        'format': 'json',
        **extra_params,
    }
    params['sig'] = make_sig(params, OK_SESSION_SECRET_KEY)

    try:
        response = requests.get(OK_API_URL, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        raise NetworkError('OK', str(e))
    except ValueError as e:
        raise ApiError('OK', f'Bad JSON from OK: {e}')

    if isinstance(data, dict) and data.get('error_code'):
        raise ApiError('OK', f"{data.get('error_code')}: {data.get('error_msg')}")

    return data


def get_upload_url(group_id):
    return ok_api_response('photosV2.getUploadUrl', {'gid': group_id, 'count': 1})


def upload_photo(upload_url, image_source):
    try:
        if isinstance(image_source, io.IOBase) or hasattr(image_source, 'read'):
            image_source.seek(0)
            files = {'pic1': image_source}
        elif isinstance(image_source, str):
            if image_source.startswith('http'):
                image_data = requests.get(image_source, timeout=30).content
                files = {'pic1': image_data}
            else:
                files = {'pic1': open(image_source, 'rb')}
        else:
            raise TypeError('Unsupported image_source type')

        response = requests.post(upload_url, files=files, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise NetworkError('OK', str(e))
    except ValueError as e:
        raise ApiError('OK', f'Bad JSON from upload: {e}')


def publish_group_post(group_id, media):
    attachment = {'media': media}
    return ok_api_response(
        'mediatopic.post',
        {
            'gid': group_id,
            'type': 'GROUP_THEME',
            'attachment': json.dumps(attachment),
        },
    )


def publish_post_to_ok(post_text, image_source=None, image_ext=None):
    """Публикация в OK. Возвращает id поста."""
    if not post_text and not image_source:
        raise ApiError('OK', 'Нет контента для публикации')

    # CHANGE (gif): для OK gif загружается как обычное фото
    if not image_ext and hasattr(image_source, 'name'):
        image_ext = os.path.splitext(str(image_source.name))[1].lower()

    media: list[dict] = []

    if post_text:
        media.append({'type': 'text', 'text': post_text})

    if image_source:
        upload_data = get_upload_url(OK_GROUP_ID)
        upload_url = upload_data['upload_url']

        upload_result = upload_photo(upload_url, image_source)
        photos_dict = upload_result.get('photos', {})

        photo_token = None
        for photo_info in photos_dict.values():
            photo_token = photo_info.get('token')
            break

        if not photo_token:
            raise ApiError('OK', 'Не удалось получить photo_token')

        media.append({'type': 'photo', 'list': [{'id': photo_token}]})

    published = publish_group_post(OK_GROUP_ID, media)

    if isinstance(published, str):
        return published

    if isinstance(published, dict) and published.get('id'):
        return published['id']

    raise ApiError('OK', f'Неожиданный ответ OK: {published}')


def delete_post_from_ok(ok_post_id):
    result = ok_api_response('mediatopic.deleteTopic', {'gid': OK_GROUP_ID, 'topic_id': ok_post_id})

    if isinstance(result, dict):
        return bool(result.get('success'))

    return bool(result is True)
