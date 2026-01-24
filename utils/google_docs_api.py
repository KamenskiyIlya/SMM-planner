import requests
import httplib2
import apiclient.discovery
from urllib.parse import urlparse
from oauth2client.service_account import ServiceAccountCredentials
from utils.google_api import normalize_text


def auth_docs():
    token_file = 'token.json'
    docs_service_urls = ['https://www.googleapis.com/auth/documents.readonly']
    credentials = ServiceAccountCredentials.from_json_keyfile_name(
        token_file, docs_service_urls
    )
    http_auth = credentials.authorize(httplib2.Http())
    return apiclient.discovery.build('docs', 'v1', http=http_auth)


def extract_doc_id(doc_url):
    return urlparse(doc_url).path.split('/')[3]


def extract_text_from_doc(document):
    text_parts = []

    for element in document['body']['content']:
        paragraph = element.get('paragraph')
        if not paragraph:
            continue

        for elem in paragraph.get('elements', []):
            text_run = elem.get('textRun')
            if text_run:
                text_parts.append(text_run['content'])

    return ''.join(text_parts)


def extract_first_image(document):
    inline_objects = document.get('inlineObjects', {})
    if not inline_objects:
        return None

    inline_object = next(iter(inline_objects.values()))
    image = inline_object['inlineObjectProperties']['embeddedObject']
    image_url = image['imageProperties']['contentUri']

    response = requests.get(image_url)
    response.raise_for_status()

    content_discription = response.headers['Content-Disposition']
    content_discription = content_discription.split('.')
    file_ext = content_discription[1].strip('"')

    image_path = f'images/from_gdoc.{file_ext}'
    with open(image_path, 'wb') as f:
        f.write(response.content)

    return image_path


def get_post_content_from_gdoc(doc_url):
    docs_service = auth_docs()
    doc_id = extract_doc_id(doc_url)

    document = docs_service.documents().get(documentId=doc_id).execute()

    raw_text = extract_text_from_doc(document)
    image_path = extract_first_image(document)

    clean_text = normalize_text(raw_text)
    return clean_text, image_path




