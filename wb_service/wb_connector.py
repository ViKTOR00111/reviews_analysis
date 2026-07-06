import time
import requests
from typing import Any

from settings import settings
from loguru import logger


class WBConnector:
    BASE_URL = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"
    TAKE = 5000
    MAX_RETRIES = 3
    RETRY_DELAY = 2

    def __init__(self):
        self.api_key = settings.API_KEY
        self.headers = {
            "Authorization": self.api_key,
        }

    def get_feedbacks(self, nm_id: int) -> list[dict[str, Any]]:
        """Выгружает все отзывы по артикулу с автоматической пагинацией."""
        all_feedbacks: list[dict[str, Any]] = []
        skip = 0

        logger.info(f"Начинаю выгрузку отзывов для nmId={nm_id}")

        while True:
            params = {
                "isAnswered": "true",
                "nmId": nm_id,
                "take": self.TAKE,
                "skip": skip,
                "order": "desc",
            }

            response = self._request_with_retry(params)
            if response is None:
                logger.error(
                    f"Не удалось получить данные для nmId={nm_id} на skip={skip}. "
                    "Прерываю выгрузку."
                )
                break

            payload = response.json()
            feedbacks = payload.get("data", {}).get("feedbacks", [])

            if not feedbacks:
                logger.info(f"Достигнут конец данных для nmId={nm_id}")
                break

            all_feedbacks.extend(feedbacks)
            logger.debug(
                f"Батч получен: {len(feedbacks)} отзывов. "
                f"Всего накоплено: {len(all_feedbacks)}"
            )

            if len(feedbacks) < self.TAKE:
                # последний батч
                break

            skip += self.TAKE
            time.sleep(0.3)  # защита от rate limit

        logger.info(
            f"Выгрузка завершена. nmId={nm_id}, всего отзывов: {len(all_feedbacks)}"
        )
        return all_feedbacks

    def _request_with_retry(self, params: dict) -> requests.Response | None:
        """HTTP-запрос с повторами при сетевых и серверных ошибках."""
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = requests.get(
                    self.BASE_URL,
                    headers=self.headers,
                    params=params,
                    timeout=60,
                )
                response.raise_for_status()
                return response

            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response is not None else None
                logger.warning(
                    f"HTTP ошибка {status} (попытка {attempt}/{self.MAX_RETRIES}): {e}"
                )
                if status in (429, 500, 502, 503, 504):
                    time.sleep(self.RETRY_DELAY * attempt)
                else:
                    return None

            except requests.exceptions.RequestException as e:
                logger.warning(
                    f"Сетевая ошибка (попытка {attempt}/{self.MAX_RETRIES}): {e}"
                )
                time.sleep(self.RETRY_DELAY * attempt)

        return None


wb_connector = WBConnector()