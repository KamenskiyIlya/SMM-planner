import time
import requests
from utils.exceptions import PublishError


NETWORK_EXCEPTIONS = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    requests.exceptions.ChunkedEncodingError,
)

def safe_call(logger, platform, fn, context, retries=3, base_sleep=1.5):
    """Выполняет fn() и возвращает (result, error_text). Логирует события."""
    for attempt in range(retries + 1):
        try:
            result = fn()
            logger.info(f"{platform} OK | {context} | result={result}")
            return result, None

        except PublishError as e:
            # ожидаемые ошибки платформ (auth, api, etc) — НЕ ретраим
            logger.warning(f"{platform} FAIL | {context} | {e.message}")
            return None, e.message

        except NETWORK_EXCEPTIONS as e:
            # ретраи только для сетевых с backoff
            logger.warning(f"{platform} NET | {context} | {type(e).__name__}: {e}")
            if attempt < retries:
                time.sleep(base_sleep * (2 ** attempt))  # 1.5s, 3s, 6s...
                continue
            return None, f"NET: {type(e).__name__}"

        except requests.exceptions.RequestException as e:
            # остальные request-ошибки НЕ ретраим бесконечно, но логируем
            logger.warning(f"{platform} NET | {context} | RequestException: {e}")
            return None, f"NET: RequestException"

        except Exception as e:
            logger.exception(f"{platform} CRASH | {context} | {type(e).__name__}: {e}")
            return None, f"CRASH: {type(e).__name__}"
