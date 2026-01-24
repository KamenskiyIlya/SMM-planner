from datetime import datetime, timedelta
from environs import Env
import os

from utils.google_api import auth_in_google_sheets, get_sheet_content, update_cell, normalize_text
from utils.google_docs_api import get_post_content_from_gdoc
from tg_publisher import publish_post_to_tg, delete_post_from_tg
# from ok_publisher import publish_post_to_ok, delete_post_from_ok
# from vk_publisher import publish_post_to_vk, delete_post_from_vk
import telegram


def check_post_datetime(post, row_number, service):
    '''Проверяет правильно формата времени и возвращает datetime.

    Проверяет правильность формата времени в таблице, добавляет
    стандартное время, если оно не было указано. Если дата и время не были указано
    выставляет в таблице нынешние дату и время. Если пользователь ввел дату
    в не правильном формате указывает об ошибке в таблице
    '''
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
                # проставляю галочки постинга обратно(на случай если пользователь снял)
                # если пост уже есть
                if post[9] and post[9] != 'Удален' and post[9] != 'Возникла ошибка':
                    update_cell(row_number, 'G', True, service)
                if post[10] and post[10] != 'Удален' and post[10] != 'Возникла ошибка':
                    update_cell(row_number, 'H', True, service)
                if post[11] and post[11] != 'Удален' and post[11] != 'Возникла ошибка':
                    update_cell(row_number, 'I', True, service)

                try:
                    want_posting_date = check_post_datetime(post, row_number, service)
                    need_publish = (
                        (
                            (post[3] == 'TRUE' and post[6] == 'FALSE' and (
                                    post[9] == 'Удален'
                                    or post[9] == 'Возникла ошибка'
                                    or not post[9]
                                )
                            )
                            or (post[4] == 'TRUE' and post[7] == 'FALSE' and (
                                    post[10] == 'Удален'
                                    or post[10] == 'Возникла ошибка'
                                    or not post[10]
                                )
                            )
                            or (post[5] == 'TRUE' and post[8] == 'FALSE' and (
                                    post[11] == 'Удален' 
                                    or post[11] == 'Возникла ошибка'
                                    or not post[11]
                                )
                            )
                        ) and now_datetime >= want_posting_date
                    )

                    if want_posting_date and need_publish:
                        posted_posts.append((row_number, post))
                except Exception as er:
                    print(f'Ошибка: {er}')

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


def posting_posts(row_number, post, post_text, image, service, image_ext):
    '''Постит все посты в указанные соцсети из списка постов на постинг'''
    # Постинг ВК
    if post[3] == 'TRUE' and post[6] == 'FALSE':
        vk_post_id = publish_post_to_vk(post_text, image)
        if vk_post_id:
            update_cell(row_number, 'G', True, service)      # Пост в VK
            update_cell(row_number, 'J', vk_post_id, service)  # ID поста VK
        else:
            update_cell(row_number, 'J', 'Возникла ошибка', service)

    # Постинг ОК
    if post[4] == 'TRUE' and post[7] == 'FALSE':
        ok_post_id = publish_post_to_ok(post_text, image)
        if ok_post_id:
            update_cell(row_number, 'H', True, service)  # Пост в OK
            update_cell(row_number, 'K', ok_post_id, service)  # ID поста в OK
        else:
            update_cell(row_number, 'K', 'Возникла ошибка', service)


    # Постинг TG    
    if post[5] == 'TRUE' and post[8] == 'FALSE':
        tg_post_id = publish_post_to_tg(image_ext, image, post_text)
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


def check_temporary_posts(content, service):
    '''Проверяет временный ли пост, и помечает в таблице когда его удалить.

    Проверяет отметил ли пользователь пост как временный, выставляет в
    таблице время его удаления. Если пришло время удаления поста, тогда
    ставит галочки на удаление из всех соцсетей.
    '''
    now_datetime = datetime.now()
    datetime_delta = timedelta(seconds=20)

    try:
        for row_number, post in enumerate(content['values'][1:], start=2):
            if post[15] == 'TRUE' and len(post) < 17:
                delete_date = now_datetime + datetime_delta
                formatted_date = delete_date.strftime('%d.%m.%Y %H:%M:%S')
                update_cell(row_number, 'Q', formatted_date, service)
            if post[15] == 'TRUE' and len(post) > 16:
                delete_date = datetime.strptime(post[16], '%d.%m.%Y %H:%M:%S')
                if now_datetime >= delete_date:
                    update_cell(row_number, 'M', True, service)
                    update_cell(row_number, 'N', True, service)
                    update_cell(row_number, 'O', True, service)
    except Exception as er:
        print(f'ошибка: {er}')



def main():
    # while:
    service = auth_in_google_sheets()
    content = get_sheet_content(service)

    check_temporary_posts(content, service)
    must_posted_posts = find_posts_must_posted(content, service)
    must_delete_posts = find_posts_must_delete(content)

    for row_number, post in must_posted_posts:
        doc_url = post[1]
        post_text, image_path = get_post_content_from_gdoc(doc_url)
        if image_path:
            image_ext = os.path.splitext(image_path)[1]

            with open(image_path, 'rb') as image:
                posting_posts(
                    row_number,
                    post,
                    post_text,
                    image,
                    service,
                    image_ext
                )
        else:
            posting_posts(
                row_number,
                post,
                post_text,
                None,
                service,
                None
            )

    delete_posts(must_delete_posts, service)


if __name__ == '__main__':
    main()
