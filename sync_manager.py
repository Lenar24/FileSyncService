"""Менеджер синхронизации файлов."""

import logging
import os
import time
from typing import Dict, Set

from cloud_storage import CloudStorage

logger = logging.getLogger(__name__)


class SyncManager:
    """Класс для управления синхронизацией файлов."""

    def __init__(self, sync_folder: str, cloud_storage: CloudStorage) -> None:
        """
        Инициализация менеджера синхронизации.

        Args:
            sync_folder: Путь к синхронизируемой папке
            cloud_storage: Экземпляр класса CloudStorage

        Raises:
            ValueError: Если синхронизируемая папка не существует
        """
        self.sync_folder = sync_folder
        self.cloud = cloud_storage
        self.file_states: Dict[str, float] = {}
        self.first_sync_done = False

        if not os.path.exists(sync_folder):
            raise ValueError(f"Синхронизируемая папка не существует: {sync_folder}")

        if not os.path.isdir(sync_folder):
            raise ValueError(f"Путь не является папкой: {sync_folder}")

    def _get_local_files(self) -> Dict[str, str]:
        """Получает список файлов в локальной папке."""
        files = {}
        try:
            for filename in os.listdir(self.sync_folder):
                filepath = os.path.join(self.sync_folder, filename)
                if os.path.isfile(filepath):
                    files[filename] = filepath
        except PermissionError:
            logger.error(f"Нет доступа к папке: {self.sync_folder}")
        except Exception as e:
            logger.error(f"Ошибка чтения папки: {e}")
        return files

    def _get_cloud_files(self) -> Set[str]:
        """Получает список файлов в облачном хранилище."""
        try:
            info = self.cloud.get_info()
            return set(info.keys())
        except Exception as e:
            logger.error(f"Ошибка получения списка файлов из облака: {e}")
            return set()

    def _full_sync(self) -> None:
        """Выполняет полную синхронизацию."""
        logger.info("Выполняется полная синхронизация...")

        local_files = self._get_local_files()
        cloud_files = self._get_cloud_files()
        local_filenames = set(local_files.keys())

        # Загружаем новые файлы
        for filename, filepath in local_files.items():
            if filename not in cloud_files:
                logger.info(f"Загрузка нового файла в облако: {filename}")
                if self.cloud.load(filepath):
                    self.file_states[filename] = os.path.getmtime(filepath)

        # Обновляем изменённые файлы
        for filename, filepath in local_files.items():
            if filename in cloud_files:
                local_mtime = os.path.getmtime(filepath)
                if filename not in self.file_states or local_mtime > self.file_states.get(
                    filename, 0
                ):
                    logger.info(f"Обновление файла в облаке: {filename}")
                    if self.cloud.reload(filepath):
                        self.file_states[filename] = local_mtime

        # Удаляем из облака файлы, которых нет локально
        for filename in cloud_files:
            if filename not in local_filenames:
                logger.info(f"Удаление файла из облака: {filename}")
                if self.cloud.delete(filename) and filename in self.file_states:
                    del self.file_states[filename]

        # Запоминаем состояние всех локальных файлов
        for filename, filepath in local_files.items():
            if filename not in self.file_states:
                self.file_states[filename] = os.path.getmtime(filepath)

        self.first_sync_done = True
        logger.info("Полная синхронизация завершена")

    def _ensure_cloud_consistency(self) -> None:
        """
        Проверяет согласованность облачной папки.

        Сравнивает локальные и облачные файлы и восстанавливает:
        1. Файлы, которые есть локально, но отсутствуют в облаке
        2. Если облачная папка пуста, а локальные файлы есть — полная синхронизация
        """
        local_files = self._get_local_files()
        cloud_files = self._get_cloud_files()

        # Случай 1: Облачная папка пуста, но локальные файлы есть
        if not cloud_files and local_files:
            logger.warning("Облачная папка пуста, выполняем полную синхронизацию...")
            self.first_sync_done = False
            self._full_sync()
            return

        # Случай 2: В облаке отсутствуют файлы, которые есть локально
        local_filenames = set(local_files.keys())
        missing_files = local_filenames - cloud_files

        if missing_files:
            logger.warning(f"В облаке отсутствуют файлы: {', '.join(missing_files)}")
            logger.info("Восстанавливаем отсутствующие файлы...")

            for filename in missing_files:
                filepath = local_files[filename]
                logger.info(f"Восстановление файла в облаке: {filename}")
                if self.cloud.load(filepath):
                    self.file_states[filename] = os.path.getmtime(filepath)

            # Перезапоминаем состояния всех локальных файлов
            for filename, filepath in local_files.items():
                if filename not in self.file_states:
                    self.file_states[filename] = os.path.getmtime(filepath)

            logger.info("Восстановление файлов завершено")

        # Случай 3: В облаке есть файлы, которых нет локально (удаляем лишние)
        cloud_filenames = set(cloud_files)
        extra_files = cloud_filenames - local_filenames

        if extra_files:
            logger.info(f"В облаке есть лишние файлы: {', '.join(extra_files)}")
            logger.info("Удаляем лишние файлы из облака...")

            for filename in extra_files:
                logger.info(f"Удаление лишнего файла из облака: {filename}")
                if self.cloud.delete(filename):
                    if filename in self.file_states:
                        del self.file_states[filename]

            logger.info("Удаление лишних файлов завершено")

    def _sync_new_files(self, local_files: Dict[str, str]) -> None:
        """Синхронизирует новые файлы из локальной папки в облако."""
        for filename, filepath in local_files.items():
            if filename not in self.file_states:
                logger.info(f"Обнаружен новый файл: {filename}")
                if self.cloud.load(filepath):
                    self.file_states[filename] = os.path.getmtime(filepath)

    def _sync_modified_files(self, local_files: Dict[str, str]) -> None:
        """Синхронизирует изменённые файлы из локальной папки в облако."""
        cloud_files = self._get_cloud_files()

        for filename, filepath in local_files.items():
            current_mtime = os.path.getmtime(filepath)
            if filename in self.file_states:
                if current_mtime > self.file_states[filename]:
                    logger.info(f"Обнаружено изменение файла: {filename}")
                    # Если файла нет в облаке — загружаем как новый
                    if filename not in cloud_files:
                        logger.info(f"Файл отсутствует в облаке, загружаем: {filename}")
                        if self.cloud.load(filepath):
                            self.file_states[filename] = current_mtime
                    elif self.cloud.reload(filepath):
                        self.file_states[filename] = current_mtime

    def _sync_deleted_files(self, local_files: Dict[str, str]) -> None:
        """Синхронизирует удалённые файлы из локальной папки в облако."""
        cloud_files = self._get_cloud_files()
        local_filenames = set(local_files.keys())

        deleted_files = set(self.file_states.keys()) - local_filenames

        for filename in deleted_files:
            if filename in cloud_files:
                logger.info(f"Обнаружено удаление файла: {filename}")
                if self.cloud.delete(filename):
                    del self.file_states[filename]

    def sync_once(self) -> None:
        """Выполняет один цикл синхронизации."""
        try:
            # Проверяем согласованность облачной папки
            self._ensure_cloud_consistency()

            if not self.first_sync_done:
                self._full_sync()
                return

            local_files = self._get_local_files()

            self._sync_new_files(local_files)
            self._sync_modified_files(local_files)
            self._sync_deleted_files(local_files)

        except Exception as e:
            logger.error(f"Ошибка во время синхронизации: {e}")

    def run_continuous(self, interval: int) -> None:
        """Запускает непрерывную синхронизацию с заданным интервалом."""
        logger.info(f"Запущена непрерывная синхронизация с интервалом {interval} сек")

        while True:
            try:
                self.sync_once()
                time.sleep(interval)
            except KeyboardInterrupt:
                logger.info("Сервис остановлен пользователем")
                break
            except Exception as e:
                logger.error(f"Критическая ошибка в цикле синхронизации: {e}")
                time.sleep(interval)
