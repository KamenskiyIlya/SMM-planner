from pprint import pprint
from datetime import datetime
from environs import Env


import httplib2
import apiclient.discovery
from oauth2client.service_account import ServiceAccountCredentials

from tg_publisher import upload_post
import telegram


SPREADSHEET_ID = '1esY5ipijX_tpqley5hz4_qAI7uQWtylWS9v52XMdht8'
MUST_POSTED_POSTS = []

# позже вызов env. спрячем под main()
env = Env()
env.read_env()
chat_id = env.str('CHAT_ID')
bot = telegram.Bot(token=env.str('TG_BOT_TOKEN'))


def auth_in_google():
    '''Экземпляр доступа api сервисов google'''
    token_file = 'token.json' #файл с ключами от сервисного акка
    service_urls = ['https://www.googleapis.com/auth/spreadsheets']
    credentials = ServiceAccountCredentials.from_json_keyfile_name(
        token_file,
        service_urls
    )
    http_auth = credentials.authorize(httplib2.Http())
    service = apiclient.discovery.build('sheets', 'v4', http=http_auth)
    return service


def get_sheet_content(service):
    '''Запрашивает данные из таблицы google'''
    content = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range='A1:Z999',
        majorDimension='ROWS'
    ).execute()
    return(content)


def find_posts_must_posted(content):
    '''Создает список постов, которые необходимо запостить(которые не постились)

    В этот список попадают только те посты, в которых стоит галочка постинга
    и у которых пришло время постинга(настоящее время >= время постинга)
    '''
    
    now_datetime = datetime.now()
    for post in content['values'][1:]:
        want_posting_date = datetime.strptime(post[2], '%d.%m.%y %H:%M')
        if (
            (
                (post[3] == 'TRUE' and post[6] == 'FALSE')
                or (post[4] == 'TRUE' and post[7] == 'FALSE')
                or (post[5] == 'TRUE' and post[8] == 'FALSE')
            ) and now_datetime >= want_posting_date
        ):
            if post not in MUST_POSTED_POSTS:
                MUST_POSTED_POSTS.append(post)
    return MUST_POSTED_POSTS


def posting_posts(must_posted_posts, service):
    for post in must_posted_posts:
        if post[3] == 'TRUE' and post[6] == 'FALSE':
            # Постинг ВК
            pass
        if post[4] == 'TRUE' and post[7] == 'FALSE':
            # Постинг ОК
            pass
        if post[5] == 'TRUE' and post[8] == 'FALSE':
            #постинг TG
            posting_tg = upload_post(
                'Привет!',
                'https://i.pinimg.com/originals/9b/26/fc/9b26fc49e07c6e4c21d00485c733ca8c.jpg',
                chat_id,
                bot
            )
            post[8] == 'TRUE'
            print(post)
            print()
        if any([posting_tg, False]):
            upload_change_in_sheet(post, service)


def upload_change_in_sheet(post, service):
    line_num = int(post[0]) + 1
    body = {
        'values' : [
            post
        ]
    }

    change = service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"A{line_num}:Z{line_num}",
        valueInputOption="RAW",
        body=body).execute()


def main():
    # while:
    service = auth_in_google()
    content = get_sheet_content(service)
    must_posted_posts = find_posts_must_posted(content)
    print(must_posted_posts)
    print()

    posting_posts(must_posted_posts, service)

if __name__ == '__main__':
    main()