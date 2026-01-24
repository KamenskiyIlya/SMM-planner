import requests
import os
from environs import Env


env = Env()
env.read_env()

VK_API_TOKEN = env.str('VK_API_TOKEN')
VK_GROUP_ID = int(env.str('VK_GROUP_ID'))  # без минуса
VK_API_VERSION = '5.199'


def upload_photo_for_wall(image_path):
    params = {
        'group_id': VK_GROUP_ID,
        'access_token': VK_API_TOKEN,
        'v': VK_API_VERSION,
    }
    response = requests.get('https://api.vk.com/method/photos.getWallUploadServer', params=params)
    response.raise_for_status()
    response_data = response.json()
    
    if 'error' in response_data:
        raise RuntimeError(response_data['error'])
    upload_url = response_data['response']['upload_url']

    if hasattr(image_path, 'read'):
        files = {'photo': image_path}
    elif isinstance(image_path, str):
        if image_path.startswith('http'):
            image_bytes = requests.get(image_path).content
            files = {'photo': image_bytes}
        else:
            files = {'photo': open(image_path, 'rb')}
    else:
        raise TypeError('Неподдерживаемый тип image_path')

    response = requests.post(upload_url, files=files)
    response.raise_for_status()
    upload_res = response.json()

    save_params = {
        'group_id': VK_GROUP_ID,
        'photo': upload_res['photo'],
        'server': upload_res['server'],
        'hash': upload_res['hash'],
        'access_token': VK_API_TOKEN,
        'v': VK_API_VERSION,
    }
    response = requests.post('https://api.vk.com/method/photos.saveWallPhoto', params=save_params)
    response.raise_for_status()
    save_response = response.json()

    photo = save_response['response'][0]
    return f"photo{photo['owner_id']}_{photo['id']}"


def publish_post_to_vk(post_text, image_path):
    if not post_text and not image_path:
        return None

    attachments = []
    if image_path:
        try:
            photo_attach = upload_photo_for_wall(image_path)
            attachments.append(photo_attach)
        except Exception:
            return None

    params = {
        'owner_id': -VK_GROUP_ID,
        'from_group': 1,
        'message': post_text or '',
        'attachments': ','.join(attachments) if attachments else None,
        'access_token': VK_API_TOKEN,
        'v': VK_API_VERSION,
    }

    response = requests.post('https://api.vk.com/method/wall.post', params=params)
    response.raise_for_status()
    response_data = response.json()

    if 'response' in response_data and 'post_id' in response_data['response']:
        return response_data['response']['post_id']
    return None


def delete_post_from_vk(post_id):
    params = {
        'owner_id': -VK_GROUP_ID,
        'post_id': post_id,
        'access_token': VK_API_TOKEN,
        'v': VK_API_VERSION,
    }
    response = requests.post('https://api.vk.com/method/wall.delete', params=params)
    response.raise_for_status()
    response_data = response.json()
    return response_data.get('response', 0) == 1