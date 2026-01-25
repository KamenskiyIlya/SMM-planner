import os
from datetime import datetime

from utils.google_api import auth_in_google_sheets, get_sheet_content, update_cell, normalize_text
from utils.google_docs_api import get_post_content_from_gdoc

from ok_publisher import publish_post_to_ok, delete_post_from_ok
from vk_publisher import publish_post_to_vk, delete_post_from_vk
from tg_publisher import publish_post_to_tg, delete_post_from_tg

from utils.logger import get_logger
from utils.safe_publish import safe_call


def _cell(post, idx, default = ''):
    """Безопасное чтение ячейки по индексу."""
    try:
        return post[idx]
    except IndexError:
        return default


def _guess_ext(image_source, fallback=None):
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


def find_posts_must_posted(content):
    """Собирает строки, которые нужно запостить (флажок соцсети TRUE, а 'Пост в ...' FALSE)."""
    posted_posts = []
    now_datetime = datetime.now()

    for row_number, post in enumerate(content.get('values', [])[1:], start=2):
        datetime_raw = _cell(post, 2)
        try:
            want_posting_date = datetime.strptime(datetime_raw, '%d.%m.%Y %H:%M:%S')
        except Exception:
            # если формат даты сломан — пропускаем (или можно писать ошибку в таблицу)
            continue

        need_publish = (
            (
                (_cell(post, 3) == 'TRUE' and _cell(post, 6) == 'FALSE')     # VK
                or (_cell(post, 4) == 'TRUE' and _cell(post, 7) == 'FALSE')  # OK
                or (_cell(post, 5) == 'TRUE' and _cell(post, 8) == 'FALSE')  # TG
            )
            and now_datetime >= want_posting_date
        )

        if need_publish:
            posted_posts.append((row_number, post))

    return posted_posts


def find_posts_must_delete(content):
    """Собирает строки, которые нужно удалить (стоит флажок удаления + есть ID поста)."""
    delete_posts = []

    for row_number, post in enumerate(content.get('values', [])[1:], start=2):
        need_delete = (
            (_cell(post, 6) == 'TRUE' and _cell(post, 12) == 'TRUE' and _cell(post, 9))         # VK
            or (_cell(post, 7) == 'TRUE' and _cell(post, 13) == 'TRUE' and _cell(post, 10))     # OK
            or (_cell(post, 8) == 'TRUE' and _cell(post, 14) == 'TRUE' and _cell(post, 11))     # TG
        )

        if need_delete:
            delete_posts.append((row_number, post))

    return delete_posts


def _load_post_content(doc_url):
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

    image_ext = _guess_ext(image_source, image_ext)
    return post_text, image_source, image_ext


def posting_posts(must_posted_posts, service):
    """Постит все посты в указанные соцсети из списка постов на постинг."""
    logger = get_logger()

    for row_number, post in must_posted_posts:
        doc_url = _cell(post, 1)
        context = {'row': row_number, 'doc': doc_url}

        try:
            post_text, image_source, image_ext = _load_post_content(doc_url)
        except Exception as e:
            logger.exception(f"GDOCS CRASH | {context} | {type(e).__name__}: {e}")
            update_cell(row_number, 'P', f"GDOCS: {type(e).__name__}", service)
            continue

        result_message = []

        # -------- VK --------
        if _cell(post, 3) == 'TRUE' and _cell(post, 6) == 'FALSE':
            vk_post_id, vk_err = safe_call(
                logger,
                'VK',
                lambda: publish_post_to_vk(post_text, image_source, image_ext),
                context=context,
            )

            if vk_post_id:
                update_cell(row_number, 'G', True, service)
                update_cell(row_number, 'J', vk_post_id, service)
                result_message.append('VK: OK')
            else:
                update_cell(row_number, 'J', 'Возникла ошибка', service)
                result_message.append(f"VK: {vk_err}")

        # -------- OK --------
        if _cell(post, 4) == 'TRUE' and _cell(post, 7) == 'FALSE':
            ok_post_id, ok_err = safe_call(
                logger,
                'OK',
                lambda: publish_post_to_ok(post_text, image_source, image_ext),
                context=context,
            )

            if ok_post_id:
                update_cell(row_number, 'H', True, service)
                update_cell(row_number, 'K', ok_post_id, service)
                result_message.append('OK: OK')
            else:
                update_cell(row_number, 'K', 'Возникла ошибка', service)
                result_message.append(f"OK: {ok_err}")

        # -------- TG --------
        if _cell(post, 5) == 'TRUE' and _cell(post, 8) == 'FALSE':
            tg_post_id, tg_err = safe_call(
                logger,
                'TG',
                lambda: publish_post_to_tg(post_text, image_source, image_ext),
                context=context
            )
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
        if _cell(post, 6) == 'TRUE' and _cell(post, 12) == 'TRUE' and _cell(post, 9):
            try:
                vk_post_id = int(_cell(post, 9))
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
        if _cell(post, 7) == 'TRUE' and _cell(post, 13) == 'TRUE' and _cell(post, 10):
            ok_post_id = _cell(post, 10)
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
        if _cell(post, 8) == 'TRUE' and _cell(post, 14) == 'TRUE' and _cell(post, 11):
            try:
                tg_post_id = int(_cell(post, 11))
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

    must_posted_posts = find_posts_must_posted(content)
    must_delete_posts = find_posts_must_delete(content)

    posting_posts(must_posted_posts, service)
    delete_posts(must_delete_posts, service)


if __name__ == '__main__':
    while:
        main()
