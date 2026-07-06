import csv
import math
import random
from pathlib import Path
from typing import Any

from loguru import logger

from settings import settings
from utils.logger import setup_logger
from wb_service import wb_connector


# Расчёт выборки
CONFIDENCE_Z = 1.96       # 95% доверительный интервал
MARGIN_ERROR = 0.03       # погрешность 3%
PROPORTION = 0.5          # максимальная дисперсия

MIN_SAMPLE_THRESHOLD = 1000   # при каком N включаем стратификацию
MAX_SAMPLE_SIZE = 1500        # потолок для иишки-анализа


def filter_feedbacks(
    feedbacks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Оставляет только отзывы, в которых есть хотя бы одно поле: text/pros/cons."""
    filtered: list[dict[str, Any]] = []

    for fb in feedbacks:
        text = (fb.get("text") or "").strip()
        pros = (fb.get("pros") or "").strip()
        cons = (fb.get("cons") or "").strip()

        if not (text or pros or cons):
            continue

        # Заменяем переносы строк на пробелы
        text = " ".join(text.split())
        pros = " ".join(pros.split())
        cons = " ".join(cons.split())

        details = fb.get("productDetails", {}) or {}
        filtered.append(
            {
                "productName": details.get("productName", ""),
                "nmId": details.get("nmId", ""),
                "productValuation": fb.get("productValuation", 0),
                "createdDate": fb.get("createdDate", ""),
                "text": text,
                "pros": pros,
                "cons": cons,
            }
        )

    logger.info(
        f"Фильтрация завершена: осталось {len(filtered)} отзывов "
        f"из {len(feedbacks)} ({len(filtered) / max(len(feedbacks), 1) * 100:.1f}%)"
    )
    return filtered


def calculate_sample_size(
    N: int,
    E: float = MARGIN_ERROR,
    Z: float = CONFIDENCE_Z,
    p: float = PROPORTION,
) -> int:
    """
    Расчёт объёма выборки с поправкой на конечную совокупность.
    Результат ограничен сверху MAX_SAMPLE_SIZE для укладывания в лимит иишки (лимит навскидку брался).
    """
    n0 = (Z ** 2 * p * (1 - p)) / (E ** 2)
    n = n0 / (1 + (n0 - 1) / N)
    return min(math.ceil(n), MAX_SAMPLE_SIZE)


def stratified_sample(
    feedbacks: list[dict[str, Any]],
    target_size: int,
) -> list[dict[str, Any]]:
    """
    Пропорциональная стратифицированная случайная выборка.
    Страты: 5 групп по productValuation (1★..5★).
    """
    # 1. Раскладываем отзывы по стратам
    strata: dict[int, list[dict[str, Any]]] = {i: [] for i in range(1, 6)}
    unknown: list[dict[str, Any]] = []

    for fb in feedbacks:
        rating = fb.get("productValuation", 0)
        if isinstance(rating, int) and 1 <= rating <= 5:
            strata[rating].append(fb)
        else:
            unknown.append(fb)

    N = len(feedbacks)
    if unknown:
        logger.warning(
            f"Найдено отзывов с некорректной оценкой (вне 1..5): {len(unknown)}"
        )

    logger.info("Распределение отзывов по стратам (оценкам):")
    for rating in range(1, 6):
        count = len(strata[rating])
        share = count / max(N, 1) * 100
        logger.info(f"  {rating}★ : {count:>5} ({share:5.1f}%)")

    # 2. Отбираем из каждой страты пропорционально
    sampled: list[dict[str, Any]] = []
    for rating in range(1, 6):
        stratum = strata[rating]
        N_h = len(stratum)
        if N_h == 0:
            continue

        # пропорциональный размер подвыборки
        n_h = round(target_size * (N_h / N))
        n_h = max(1, min(n_h, N_h))  # не больше, чем есть в страте

        sampled_stratum = random.sample(stratum, n_h)
        sampled.extend(sampled_stratum)
        logger.debug(f"Страта {rating}★: отобрано {n_h} из {N_h}")

    random.shuffle(sampled)
    logger.info(f"Итоговый размер выборки: {len(sampled)}")
    return sampled


def save_to_csv(feedbacks: list[dict[str, Any]], nm_id: int) -> Path:
    """Сохраняет выборку в CSV в текущей директории."""
    filename = f"{nm_id}_reviews.csv"
    filepath = Path.cwd() / filename

    fieldnames = [
        "productName",
        "nmId",
        "productValuation",
        "createdDate",
        "text",
        "pros",
        "cons",
    ]

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(feedbacks)

    logger.info(f"Файл сохранён: {filepath}")
    return filepath


def process_article(nm_id: int) -> None:
    """Полный pipeline обработки одного артикула."""
    logger.info("=" * 60)
    logger.info(f"Обработка артикула: {nm_id}")
    logger.info("=" * 60)

    # Выгрузка
    raw_feedbacks = wb_connector.get_feedbacks(nm_id)
    if not raw_feedbacks:
        logger.warning(f"По артикулу {nm_id} отзывов не получено. Пропуск.")
        return

    # Фильтрация
    filtered = filter_feedbacks(raw_feedbacks)
    if not filtered:
        logger.warning(
            f"После фильтрации по артикулу {nm_id} не осталось содержательных отзывов."
        )
        return

    # Выборка
    N = len(filtered)
    if N > MIN_SAMPLE_THRESHOLD:
        target_size = calculate_sample_size(N)
        logger.info(
            f"N={N} превышает порог {MIN_SAMPLE_THRESHOLD}. "
            f"Применяю стратифицированную выборку, целевой размер: {target_size}"
        )
        sample = stratified_sample(filtered, target_size)
    else:
        logger.info(f"N={N} <= {MIN_SAMPLE_THRESHOLD}. Беру все отзывы целиком.")
        sample = filtered

    # Сохранение
    save_to_csv(sample, nm_id)


def main() -> None:
    setup_logger(settings)
    logger.info("Запуск pipeline выгрузки отзывов WB")
    logger.info(f"Артикулы в работе: {settings.ARTICLES}")

    for nm_id in settings.ARTICLES:
        try:
            process_article(nm_id)
        except Exception as e:
            logger.exception(f"Критическая ошибка при обработке nmId={nm_id}: {e}")

    logger.info("Pipeline завершён.")


if __name__ == "__main__":
    main()