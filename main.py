"""Главный модуль сервиса синхронизации файлов."""

A
import configparser
import logging
import os
import sys

from cloud_storage import CloudStorage
from logger_setup import setup_logger
from sync_manager import SyncManager


def load_config() -> dict:
    """
    Загружает конфигурацию из config.ini файла.

    Returns:
        Словарь с параметрами конфигурации

    Raises:
        ValueError: Если обязательные параметры отсутствуют или файл не найден
    """
    config = configparser.ConfigParser()
    config_path = "config.ini"

    if not os.path.exists(config_path):
        raise ValueError(
            "Файл config.ini не найден. Создайте файл config.ini с необходимыми параметрами.\n"
            "Пример содержимого:\n"
            "[Settings]\n"
            "sync_folder = /path/to/sync/folder\n"
            "cloud_folder_name = CloudBackup\n"
            "yandex_token = your_token_here\n"
            "sync_interval = 60\n"
            "log_file = sync_service.log"
        )

    config.read(config_path, encoding="utf-8")

    if not config.has_section("Settings"):
        raise ValueError(
            "В файле config.ini отсутствует секция [Settings]. "
            "Добавьте секцию [Settings] с параметрами."
        )

    required_params = [
        "sync_folder",
        "cloud_folder_name",
        "yandex_token",
        "sync_interval",
        "log_file",
    ]

    missing_params = []
    for param in required_params:
        if not config.has_option("Settings", param):
            missing_params.append(param)

    if missing_params:
        raise ValueError(
            f"Отсутствуют обязательные параметры в config.ini: {', '.join(missing_params)}"
        )

    sync_folder = config.get("Settings", "sync_folder")
    cloud_folder = config.get("Settings", "cloud_folder_name")
    yandex_token = config.get("Settings", "yandex_token")
    sync_interval = config.get("Settings", "sync_interval")
    log_file = config.get("Settings", "log_file")

    try:
        sync_interval = int(sync_interval)
        if sync_interval <= 0:
            raise ValueError("sync_interval должен быть положительным числом")
    except ValueError:
        raise ValueError("sync_interval должен быть целым положительным числом")

    return {
        "sync_folder": sync_folder,
        "cloud_folder": cloud_folder,
        "yandex_token": yandex_token,
        "sync_interval": sync_interval,
        "log_file": log_file,
    }


def main() -> None:
    """Главная функция программы."""
    try:
        config = load_config()

        setup_logger(config["log_file"])
        logger = logging.getLogger()
        logger.info(f"Синхронизируемая папка: {config['sync_folder']}")
        logger.info(f"Облачная папка: {config['cloud_folder']}")

        try:
            cloud = CloudStorage(token=config["yandex_token"], folder_name=config["cloud_folder"])
        except ValueError as e:
            logger.error(f"Ошибка подключения к облачному хранилищу: {e}")
            sys.exit(1)

        try:
            sync_manager = SyncManager(sync_folder=config["sync_folder"], cloud_storage=cloud)
        except ValueError as e:
            logger.error(f"Ошибка инициализации менеджера синхронизации: {e}")
            sys.exit(1)

        sync_manager.sync_once()
        sync_manager.run_continuous(config["sync_interval"])

    except ValueError as e:
        print(f"Ошибка конфигурации: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Неожиданная ошибка: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
