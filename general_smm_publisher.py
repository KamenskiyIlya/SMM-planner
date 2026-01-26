import os
from datetime import datetime, timedelta

from utils.google_api import auth_in_google_sheets, get_sheet_content, update_cell, normalize_text
from utils.google_docs_api import get_post_content_from_gdoc

from ok_publisher import publish_post_to_ok, delete_post_from_ok
from vk_publisher import publish_post_to_vk, delete_post_from_vk
from tg_publisher import publish_post_to_tg, delete_post_from_tg

from utils.logger import get_logger
from utils.safe_publish import safe_call


def check_post_datetime(post, row_number, service):
    """Проверяет правильно формата времени и возвращает datetime.

    Проверяет правильность формата времени в таблице, добавляет
    стандартное время, если оно не было указано. Если дата и время
    не были указано выставляет в таблице нынешние дату и время.
    Если пользователь ввел дату в не правильном формате указывает
    об ошибке в таблице.
    """
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
            # Дописываем стандартное время для постинга, если не указали
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
            update_cell(
                row_number,
                'C',
                'Указан не верный формат даты',
                service
            )
            return


def read_cell(post, idx, default=''):
    """Безопасное чтение ячейки по индексу."""
    try:
        return post[idx]
    except IndexError:
        return default


def guess_extstension(image_source, fallback=None):
    """Пытается определить расширение файла по пути/URL/файлу."""
    if fallback:
        return fallback

    if hasattr(image_source, 'name'):
        _, ext = os.path.splitext(str(getattr(image_source, 'name')))
        return ext.lower() if ext else None

    if isinstance(image_source, str):
        # если URL с querystring
        path = image_source.split('?', 1)[0]
        _, ext = os.path.splitext(path)
        return ext.lower() if ext else None

    return None


def find_posts_must_posted(content, service):
    """Собирает строки, которые нужно запостить (флажок соцсети TRUE,
    а 'Пост в ...' FALSE). В этот список попадают только те посты,
    в которых стоит галочка постинга и у которых пришло время постинга
    (настоящее время >= время постинга).
    """
    posted_posts = []
    now_datetime = datetime.now()

    for row_number, post in enumerate(content.get('values', [])[1:], start=2):
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
    """
    Собирает строки, которые нужно удалить
    (стоит флажок удаления + есть ID поста).
    """
    delete_posts = []
    for row_number, post in enumerate(content.get('values', [])[1:], start=2):
        need_delete = (
            (read_cell(post, 6) == 'TRUE' and read_cell(post, 12) == 'TRUE' and read_cell(post, 9))         # VK
            or (read_cell(post, 7) == 'TRUE' and read_cell(post, 13) == 'TRUE' and read_cell(post, 10))     # OK
            or (read_cell(post, 8) == 'TRUE' and read_cell(post, 14) == 'TRUE' and read_cell(post, 11))     # TG
        )
        if need_delete:
            delete_posts.append((row_number, post))
    return delete_posts


def check_temporary_posts(content, service):
    """Проверяет временный ли пост, и помечает в таблице когда его удалить.

    Проверяет отметил ли пользователь пост как временный, выставляет в
    таблице время его удаления. Если пришло время удаления поста, тогда
    ставит галочки на удаление из всех соцсетей.
    """
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
                    if read_cell(post, 6) == 'TRUE':
                        update_cell(row_number, 'M', True, service)
                    if read_cell(post, 7) == 'TRUE':
                        update_cell(row_number, 'N', True, service)
                    if read_cell(post, 8) == 'TRUE':
                        update_cell(row_number, 'O', True, service)
                    update_cell(row_number, 'P', False, service)
                    update_cell(row_number, 'Q', '', service)
    except Exception as er:
        print(f'ошибка: {er}')


def load_post_content(doc_url):
    """Достаёт текст+картинку из Google Docs.

    Ожидаемые варианты возврата get_post_content_from_gdoc:
      - (text, image_source)
      - (text, image_source, image_ext)
    """
    result = get_post_content_from_gdoc(doc_url)

    post_text = None
    image_source = None
    image_ext = None

    if isinstance(result, tuple):
        if len(result) >= 1:
            post_text = result[0]
        if len(result) >= 2:
            image_source = result[1]
        if len(result) >= 3:
            image_ext = result[2]

    if post_text:
        post_text = normalize_text(post_text)

    image_ext = guess_extstension(image_source, image_ext)
    return post_text, image_source, image_ext


def posting_posts(must_posted_posts, service):
    """Постит все посты в указанные соцсети из списка постов на постинг."""
    logger = get_logger()

    for row_number, post in must_posted_posts:
        doc_url = read_cell(post, 1)
        context = {'row': row_number, 'doc': doc_url}

        try:
            post_text, image_source, image_ext = load_post_content(doc_url)
        except Exception as e:
            logger.exception(f"GDOCS CRASH | {context} | {type(e).__name__}: {e}")
            update_cell(row_number, 'P', f"GDOCS: {type(e).__name__}", service)
            continue

        result_message = []

        # -------- VK --------
        if read_cell(post, 3) == 'TRUE' and read_cell(post, 6) == 'FALSE':
            vk_post_id, vk_err = safe_call(
                logger,
                'VK',
                lambda: publish_post_to_vk(post_text, image_source, image_ext),
                context=context,
            )
            # Убирает флажок удалить если такой стоял
            update_cell(row_number, 'M', False, service)

            if vk_post_id:
                update_cell(row_number, 'G', True, service)
                update_cell(row_number, 'J', vk_post_id, service)
                result_message.append('VK: OK')
            else:
                update_cell(row_number, 'J', 'Возникла ошибка', service)
                result_message.append(f"VK: {vk_err}")

        # -------- OK --------
        if read_cell(post, 4) == 'TRUE' and read_cell(post, 7) == 'FALSE':
            ok_post_id, ok_err = safe_call(
                logger,
                'OK',
                lambda: publish_post_to_ok(post_text, image_source, image_ext),
                context=context,
            )

            # Убирает флажок удалить если такой стоял
            update_cell(row_number, 'N', False, service)

            if ok_post_id:
                update_cell(row_number, 'H', True, service)
                update_cell(row_number, 'K', ok_post_id, service)
                result_message.append('OK: OK')
            else:
                update_cell(row_number, 'K', 'Возникла ошибка', service)
                result_message.append(f"OK: {ok_err}")

        # -------- TG --------
        if read_cell(post, 5) == 'TRUE' and read_cell(post, 8) == 'FALSE':
            tg_post_id, tg_err = safe_call(
                logger,
                'TG',
                lambda: publish_post_to_tg(post_text, image_source, image_ext),
                context=context
            )

            # Убирает флажок удалить если такой стоял
            update_cell(row_number, 'O', False, service)

            if tg_post_id:
                update_cell(row_number, 'I', True, service)
                update_cell(row_number, 'L', tg_post_id, service)
                result_message.append('TG: OK')
            else:
                update_cell(row_number, 'L', 'Возникла ошибка', service)
                result_message.append(f"TG: {tg_err}")


def delete_posts(must_delete_posts, service):
    """Удаляет посты из соцсетей, которые помечены на удаление."""
    logger = get_logger()

    for row_number, post in must_delete_posts:
        context = {'row': row_number}
        result_message = []

        # -------- VK --------
        if read_cell(post, 6) == 'TRUE' and read_cell(post, 12) == 'TRUE' and read_cell(post, 9):
            try:
                vk_post_id = int(read_cell(post, 9))
            except ValueError:
                vk_post_id = None

            if vk_post_id:
                deleted, err = safe_call(logger, 'VK', lambda: delete_post_from_vk(vk_post_id), context=context)
                if deleted:
                    update_cell(row_number, 'D', False, service)
                    update_cell(row_number, 'G', False, service)
                    update_cell(row_number, 'J', '', service)
                    update_cell(row_number, 'M', False, service)
                    result_message.append('VK: DELETED')
                else:
                    result_message.append(f"VK: {err or 'не удален'}")

        # -------- OK --------
        if read_cell(post, 7) == 'TRUE' and read_cell(post, 13) == 'TRUE' and read_cell(post, 10):
            ok_post_id = read_cell(post, 10)
            deleted, err = safe_call(logger, 'OK', lambda: delete_post_from_ok(ok_post_id), context=context)

            if deleted:
                update_cell(row_number, 'E', False, service)
                update_cell(row_number, 'H', False, service)
                update_cell(row_number, 'K', '', service)
                update_cell(row_number, 'N', False, service)
                result_message.append('OK: DELETED')
            else:
                result_message.append(f"OK: {err or 'не удален'}")

        # -------- TG --------
        if read_cell(post, 8) == 'TRUE' and read_cell(post, 14) == 'TRUE' and read_cell(post, 11):
            try:
                tg_post_id = int(read_cell(post, 11))
            except ValueError:
                tg_post_id = None

            if tg_post_id:
                deleted, err = safe_call(logger, 'TG', lambda: delete_post_from_tg(tg_post_id), context=context)

                if deleted:
                    update_cell(row_number, 'F', False, service)
                    update_cell(row_number, 'I', False, service)
                    update_cell(row_number, 'L', '', service)
                    update_cell(row_number, 'O', False, service)
                    result_message.append('TG: DELETED')
                else:
                    result_message.append(f"TG: {err or 'не удален'}")


def main():
    service = auth_in_google_sheets()
    content = get_sheet_content(service)

    check_temporary_posts(content, service)
    must_posted_posts = find_posts_must_posted(content, service)
    must_delete_posts = find_posts_must_delete(content)

    posting_posts(must_posted_posts, service)
    delete_posts(must_delete_posts, service)


if __name__ == '__main__':
    while True:
        main()
