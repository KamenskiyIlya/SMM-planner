import requests
import json
from environs import Env
from utils.ok_md5hex import get_md5, make_sig

env = Env()
env.read_env()

global application_key, session_secret_key, access_token

application_key = env.str('OK_APP_PUBLIC_KEY')
session_secret_key = env.str('OK_SESSION_SECRET_KEY')
access_token = env.str('OK_ACCESS_TOKEN')
group_id=env.str('OK_GROUP_ID')

def ok_api_response(method, extra_params):
    params = {
    'method': method,
    'application_key': application_key,
    'access_token': access_token,
    'format': 'json',
    **extra_params,
    }
    params['sig'] = make_sig(params, session_secret_key)
    url = 'https://api.ok.ru/fb.do'
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()


def get_upload_url(group_id):
    return ok_api_response(
        'photosV2.getUploadUrl',
        {
            'gid': group_id,
            'count': 1,
        }
    )


def upload_photo(upload_url, image_path):
    with open(image_path, 'rb') as image_file:
        response = requests.post(
            upload_url,
            files={'pic1': image_file}
        )
    response.raise_for_status()
    return response.json()


def publish_group_post(group_id, post_text, photo_token):
    media = [
        {
            'type': 'text',
            'text': post_text,
        },
        {
            'type': 'photo',
            'list': [
                {'id': photo_token}
            ]
        }
    ]
    attachment = {
        'media': media
    }
    return ok_api_response(
        'mediatopic.post',
        {
            'gid': group_id,
            'type': 'GROUP_THEME',
            'attachment': json.dumps(attachment),
        }
    )


def delete_post_from_ok(ok_posted_id):
    params = {
        'application_key': application_key,
        'method': 'mediatopic.deleteTopic',
        'gid': group_id,
        'topic_id': ok_posted_id,
        'format': 'json',
    }

    params['sig'] = make_sig(params, session_secret_key)
    params['access_token'] = access_token
    url = 'https://api.ok.ru/fb.do'
    response = requests.post(url, data=params)
    response.raise_for_status()

    result = response.json()
    print('OK DELETE RESPONSE:', result)

    return bool(result.get('success'))


def publish_post_to_ok(post_text, image_path):
    # 1. Получаем upload URL для загрузки изображения:
    upload_data = get_upload_url(group_id)
    upload_url = upload_data['upload_url']

 	# 2. Загружаем фото и получаем обязательный Photo Token:
    upload_result = upload_photo(upload_url, image_path)
    photos_dict = upload_result['photos']

    for photo_info in photos_dict.values():
        photo_token = photo_info['token']
        break

    # 3. Публикуем пост:
    published_post = publish_group_post(group_id, post_text, photo_token)
    
    return published_post
