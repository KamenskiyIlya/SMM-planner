from pprint import pprint
from datetime import datetime
from environs import Env

from utils.google_api import auth_in_google_sheets, get_sheet_content, update_cell, normalize_text
from utils.google_docs_api import get_post_content_from_gdoc
from tg_publisher import publish_post_to_tg, delete_post_from_tg
from ok_publisher import publish_post_to_ok, delete_post_from_ok
from vk_publisher import publish_post_to_vk, delete_post_from_vk
import telegram


def check_post_datetime(post, row_number, service):
    now_datetime = datetime.now()
    try:
        if not post[2]:
            want_posting_date = now_datetime
            formatted_date = want_posting_date.strftime('%d.%m.%Y %H:%M:%S')
            update_cell(row_number, 'C', formatted_date, service)
            return want_posting_date
        if post[2]:
            want_posting_date = datetime.strptime(post[2], '%d.%m.%Y %H:%M:%S')
            return want_posting_date
    except ValueError:
        try:
            # Дописываем стандартное время для постинга, если пользователь не указал
            sheet_date = datetime.strptime(post[2], '%d.%m.%Y')
            base_publicate_hour = 13
            want_posting_date = datetime(
                sheet_date.year,
                sheet_date.month,
                sheet_date.day,
                base_publicate_hour
            )
            formatted_date = want_posting_date.strftime('%d.%m.%Y %H:%M:%S')
            
            update_cell(row_number, 'C', formatted_date, service)
            return want_posting_date
        except ValueError:
            # Информируем пользователя о не правильном формате даты и времени
            update_cell(row_number, 'C', 'Указан не верный формат даты', service)
            return

def find_posts_must_posted(content, service):
    '''Создает список постов, которые необходимо запостить(которые не постились)

    В этот список попадают только те посты, в которых стоит галочка постинга
    и у которых пришло время постинга(настоящее время >= время постинга)
    '''
    posted_posts = []
    now_datetime = datetime.now()

    for row_number, post in enumerate(content['values'][1:], start=2):
            if post[1]:
                try:
                    want_posting_date = check_post_datetime(post, row_number, service)
                    need_publish = (
                        (
                            (post[3] == 'TRUE' and post[6] == 'FALSE' and not post[9])
                            or (post[4] == 'TRUE' and post[7] == 'FALSE' and not post[10])
                            or (post[5] == 'TRUE' and post[8] == 'FALSE' and not post[11])
                        ) and now_datetime >= want_posting_date
                    )

                    if want_posting_date and need_publish:
                        posted_posts.append((row_number, post))
                except Exception as er:
                    print(f'Ошибка: {er}')

            # проставляю галочки постинга обратно(на случай если пользователь снял)
            # если пост уже есть
            if post[9]:
                update_cell(row_number, 'G', True, service)
            if post[10]:
                update_cell(row_number, 'H', True, service)
            if post[11]:
                update_cell(row_number, 'I', True, service)

    return posted_posts


def find_posts_must_delete(content):
    '''Собирает список постов, которые нужно удалить(стоит флажок в таблице)'''
    delete_posts = []

    for row_number, post in enumerate(content['values'][1:], start=2):
        need_delete = (
            (post[6] == 'TRUE' and post[12] == 'TRUE' and post[9])
            or (post[7] == 'TRUE' and post[13] == 'TRUE' and post[10])
            or (post[8] == 'TRUE' and post[14] == 'TRUE' and post[11])
        )

        if need_delete:
            delete_posts.append((row_number, post))
    return delete_posts


def posting_posts(row_number, post, post_text, image_path, service):
    '''Постит все посты в указанные соцсети из списка постов на постинг'''
    # Постинг ВК
    if post[3] == 'TRUE' and post[6] == 'FALSE':
        vk_post_id = publish_post_to_vk(post_text, image_path)
        if vk_post_id:
            update_cell(row_number, 'G', True, service)      # Пост в VK
            update_cell(row_number, 'J', vk_post_id, service)  # ID поста VK
        else:
            update_cell(row_number, 'J', 'Возникла ошибка', service)

    # Постинг ОК
    if post[4] == 'TRUE' and post[7] == 'FALSE':
        ok_post_id = publish_post_to_ok(post_text, image_path)
        if ok_post_id:
            update_cell(row_number, 'H', True, service)  # Пост в OK
            update_cell(row_number, 'K', ok_post_id, service)  # ID поста в OK
        else:
            update_cell(row_number, 'K', 'Возникла ошибка', service)


    # Постинг TG    
    if post[5] == 'TRUE' and post[8] == 'FALSE':
        tg_post_id = publish_post_to_tg(post_text, image_path)
        if tg_post_id:
            update_cell(row_number, 'I', True, service)
            update_cell(row_number, 'L', tg_post_id, service)
        else:
            update_cell(row_number, 'L', 'Возникла ошибка', service)

def delete_posts(must_delete_posts, service):
    '''Удаляет посты из соцсетей, которые помечены на удаление'''
    for row_number, post in must_delete_posts:

        # Удаление из ВК
        if post[6] == 'TRUE' and post[12] == 'TRUE':
            vk_post_id = post[9]
            deleted = delete_post_from_vk(vk_post_id)

            if deleted:
                update_cell(row_number, 'D', False, service)    # флажок необходимости постинга
                update_cell(row_number, 'G', False, service)    # флажок подтверждения постинга
                update_cell(row_number, 'J', 'Удален', service)    # ID поста
                update_cell(row_number, 'M', False, service)    # флажок удаления

        # Удаление из OK
        if post[7] == 'TRUE' and post[13] == 'TRUE':
            ok_post_id = post[10]
            deleted = delete_post_from_ok(ok_post_id)
        
            if deleted:
                update_cell(row_number, 'E', False, service)    # флажок необходимости постинга
                update_cell(row_number, 'H', False, service)    # флажок подтверждения постинга
                update_cell(row_number, 'K', 'Удален', service)    # ID поста
                update_cell(row_number, 'N', False, service)    # флажок удаления

        # Удаление из TG
        if post[8] == 'TRUE' and post[14] == 'TRUE':
            tg_post_id = int(post[11])
            deleted = delete_post_from_tg(tg_post_id)

            if deleted:
                update_cell(row_number, 'F', False, service)    # флажок необходимости постинга
                update_cell(row_number, 'I', False, service)    # флажок подтверждения постинга
                update_cell(row_number, 'L', 'Удален', service)    # ID поста
                update_cell(row_number, 'O', False, service)    # флажок удаления


def main():
    # while:
    service = auth_in_google_sheets()
    content = get_sheet_content(service)

    must_posted_posts = find_posts_must_posted(content, service)
    must_delete_posts = find_posts_must_delete(content)

    for row_number, post in must_posted_posts:
        doc_url = post[1]
        post_text, image_path = get_post_content_from_gdoc(doc_url)

        with open(image_path, 'rb') as image:
            posting_posts(
                row_number,
                post,
                post_text,
                image,
                service
            )

    delete_posts(must_delete_posts, service)


if __name__ == '__main__':
    main()
