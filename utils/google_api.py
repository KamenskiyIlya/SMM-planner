from datetime import datetime
import re
import httplib2
import apiclient.discovery
from oauth2client.service_account import ServiceAccountCredentials

SPREADSHEET_ID = '1esY5ipijX_tpqley5hz4_qAI7uQWtylWS9v52XMdht8'


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


def update_cell(row, column, value, service):
    body = {
        'values': [[value]]
    }
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f'{column}{row}',
        valueInputOption='RAW',
        body=body
    ).execute()


def normalize_text(text):
    result = []
    open_quote = True
    for char in text:
        if char == '"':
            if open_quote:
                result.append('«')
            else:
                result.append('»')
            open_quote = not open_quote
        else:
            result.append(char)
    text = ''.join(result)
    text = text.replace(' - ', ' — ')
    text = re.sub(r'\s{2,}', ' ', text)
    return text
