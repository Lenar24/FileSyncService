"""Настройка логирования с использованием модуля logging."""

import logging
import sys
from datetime import datetime


def setup_logger(log_file_path: str) -> None:
    """
    Настройка логгера с записью в файл и выводом в консоль.
    Args:
        log_file_path: Путь к файлу лога
    """
    # Создаём логгер
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Удаляем старые обработчики, если есть
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Формат логов
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Обработчик для файла
    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Обработчик для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.info(f"Сервис синхронизации запущен в {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
