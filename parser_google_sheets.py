from pprint import pprint
from datetime import datetime
from environs import Env

from utils.google_api import auth_in_google, get_sheet_content, update_cell, normalize_text
from tg_publisher import upload_post
from ok_publisher import publish_post_to_ok, delete_post_from_ok
import telegram



# позже вызов env. спрячем под main()
# env = Env()
# env.read_env()
# chat_id = env.str('CHAT_ID')
# bot = telegram.Bot(token=env.str('TG_BOT_TOKEN'))


def find_posts_must_posted(content):
    '''Создает список постов, которые необходимо запостить(которые не постились)

    В этот список попадают только те посты, в которых стоит галочка постинга
    и у которых пришло время постинга(настоящее время >= время постинга)
    '''
    posted_post = []
    now_datetime = datetime.now()

    for row_number, post in enumerate(content['values'][1:], start=2):
        want_posting_date = datetime.strptime(post[2], '%d.%m.%y %H:%M')

        need_publish = (
            (
                (post[3] == 'TRUE' and post[6] == 'FALSE')
                or (post[4] == 'TRUE' and post[7] == 'FALSE')
                or (post[5] == 'TRUE' and post[8] == 'FALSE')
            ) and now_datetime >= want_posting_date
        )

        need_delete = (
            (post[6] == 'TRUE' and post[12] == 'TRUE' and post[9])
            or (post[7] == 'TRUE' and post[13] == 'TRUE' and post[10])
            or (post[8] == 'TRUE' and post[14] == 'TRUE' and post[11])
        )

        if need_publish or need_delete:
            posted_post.append((row_number, post))
    return posted_post


def posting_posts(must_posted_posts, post_text, image_path, service):
    for row_number, post in must_posted_posts:
        if post[3] == 'TRUE' and post[6] == 'FALSE':
            # Постинг ВК
            pass
        if post[4] == 'TRUE' and post[7] == 'FALSE':
            # Постинг ОК
            ok_post_id = publish_post_to_ok(post_text, image_path)
            if ok_post_id:
                update_cell(row_number, 'H', True, service)  # Пост в OK
                update_cell(row_number, 'K', ok_post_id, service)  # ID поста в OK

        # Удаление поста
        if post[7] == 'TRUE' and post[13] == 'TRUE' and post[10]:
            ok_posted_id = post[10]
            deleted = delete_post_from_ok(ok_posted_id)
        
            if deleted:
                update_cell(row_number, 'H', False,service)   # Пост в OK
                update_cell(row_number, 'K', 'Удалён', service)      # ID поста

            
        # if post[5] == 'TRUE' and post[8] == 'FALSE':
        #     #постинг TG
        #     tg_post_id = upload_post(
        #         'Привет!',
        #         'https://i.pinimg.com/originals/9b/26/fc/9b26fc49e07c6e4c21d00485c733ca8c.jpg',
        #         chat_id,
        #         bot
        #     )
        #     if tg_post_id:
        #         update_cell(row_number, 'I', True, service)
        #         update_cell(row_number, 'L', tg_post_id, service)


def main():
    # while:
    service = auth_in_google()
    content = get_sheet_content(service)
    
    must_posted_posts = find_posts_must_posted(content)
    print(must_posted_posts)
    print()
    text = '"Хаббл" - Космический телескоп '    # !!! Сюда нужно чтобы попадал текст с GOOGLE DOCKS
    post_text = normalize_text(text)
    image_path = 'images/Habble.jpeg'           # !!! Сюда нужно чтобы попадали изображения с GOOGLE DOCKS
    posting_posts(must_posted_posts, post_text, image_path, service)

if __name__ == '__main__':
    main()