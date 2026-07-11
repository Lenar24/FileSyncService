"""Модуль для работы с облачным хранилищем Yandex.Disk."""

import logging
import os
from typing import Dict

import requests

logger = logging.getLogger(__name__)


class CloudStorage:
    """Класс для взаимодействия с облачным хранилищем Yandex.Disk."""

    def __init__(self, token: str, folder_name: str) -> None:
        """
        Инициализация подключения к облачному хранилищу.

        Args:
            token: Токен доступа к Yandex.Disk
            folder_name: Имя папки в облачном хранилище

        Raises:
            ValueError: Если токен невалидный или папка недоступна
        """
        self.token = token
        self.folder_name = folder_name
        self.base_url = "https://cloud-api.yandex.net/v1/disk"
        self.headers = {
            "Authorization": f"OAuth {token}",
            "Content-Type": "application/json",
        }

        if not self._validate_token():
            raise ValueError("Неверный токен доступа. Проверьте правильность токена.")

        self._ensure_folder_exists()

    def _validate_token(self) -> bool:
        """Проверяет валидность токена доступа."""
        try:
            response = requests.get(f"{self.base_url}/", headers=self.headers, timeout=10)
            return response.status_code == 200
        except requests.Timeout:
            logger.error("Таймаут при проверке токена")
            return False
        except requests.RequestException:
            return False

    def _ensure_folder_exists(self) -> None:
        """Создаёт папку в облачном хранилище, если её нет."""
        try:
            response = requests.get(
                f"{self.base_url}/resources",
                headers=self.headers,
                params={"path": f"disk:/{self.folder_name}"},
                timeout=10,
            )

            if response.status_code == 404:
                create_response = requests.put(
                    f"{self.base_url}/resources",
                    headers=self.headers,
                    params={"path": f"disk:/{self.folder_name}"},
                    timeout=10,
                )
                if create_response.status_code == 201:
                    logger.info(f"Создана папка в облаке: disk:/{self.folder_name}")
                else:
                    raise ValueError(
                        f"Не удалось создать папку в облаке. "
                        f"Статус: {create_response.status_code}"
                    )
            elif response.status_code != 200:
                raise ValueError(
                    f"Ошибка проверки папки в облаке. " f"Статус: {response.status_code}"
                )
            else:
                logger.info(f"Папка в облаке уже существует: disk:/{self.folder_name}")
        except requests.Timeout:
            logger.error("Таймаут при проверке папки в облаке")
            raise ValueError("Таймаут при проверке папки в облаке")
        except requests.RequestException as e:
            raise ValueError(f"Ошибка сети при проверке папки в облаке: {e}")

    def _ensure_folder_exists_silent(self) -> bool:
        """
        Восстанавливает папку в облаке без логирования ошибок.

        Returns:
            True если папка создана или уже существует, иначе False
        """
        try:
            response = requests.get(
                f"{self.base_url}/resources",
                headers=self.headers,
                params={"path": f"disk:/{self.folder_name}"},
                timeout=10,
            )

            if response.status_code == 404:
                create_response = requests.put(
                    f"{self.base_url}/resources",
                    headers=self.headers,
                    params={"path": f"disk:/{self.folder_name}"},
                    timeout=10,
                )
                if create_response.status_code == 201:
                    logger.info(f"Восстановлена папка в облаке: disk:/{self.folder_name}")
                    return True
                return False
            return response.status_code == 200
        except requests.Timeout:
            logger.error("Таймаут при восстановлении папки")
            return False
        except Exception:
            return False

    def _is_folder_not_found_error(self, error_data) -> bool:
        """
        Проверяет, является ли ошибка "папка не найдена".

        Args:
            error_data: Данные ошибки из ответа API

        Returns:
            True если ошибка связана с отсутствием папки
        """
        error_str = str(error_data)
        return "DiskNotFoundError" in error_str or "DiskPathDoesntExistsError" in error_str

    def load(self, path: str) -> bool:
        """
        Загружает файл в облачное хранилище.

        Args:
            path: Путь к файлу на локальном компьютере

        Returns:
            True если загрузка успешна, иначе False
        """
        try:
            filename = os.path.basename(path)
            cloud_path = f"disk:/{self.folder_name}/{filename}"

            logger.info(f"Загрузка файла в облако: {filename} -> {cloud_path}")

            try:
                upload_url_response = requests.get(
                    f"{self.base_url}/resources/upload",
                    headers=self.headers,
                    params={"path": cloud_path, "overwrite": False},
                    timeout=10,
                )
            except requests.Timeout:
                logger.error(f"Таймаут при получении URL для загрузки файла {filename}")
                return False
            except requests.RequestException as e:
                logger.error(f"Ошибка запроса при получении URL для загрузки: {e}")
                return False

            # Если папка не существует — восстанавливаем её
            if upload_url_response.status_code == 404:
                try:
                    error_data = upload_url_response.json()
                except ValueError:
                    error_data = {}
                if self._is_folder_not_found_error(error_data):
                    logger.warning("Папка в облаке не существует, восстанавливаем...")
                    if self._ensure_folder_exists_silent():
                        try:
                            upload_url_response = requests.get(
                                f"{self.base_url}/resources/upload",
                                headers=self.headers,
                                params={"path": cloud_path, "overwrite": False},
                                timeout=10,
                            )
                        except requests.Timeout:
                            logger.error(
                                f"Таймаут при повторном получении URL для загрузки {filename}"
                            )
                            return False
                        except requests.RequestException as e:
                            logger.error(f"Ошибка запроса при повторном получении URL: {e}")
                            return False

            if upload_url_response.status_code != 200:
                logger.error(f"Ошибка получения URL для загрузки: {upload_url_response.text}")
                return False

            upload_url = upload_url_response.json().get("href")

            try:
                with open(path, "rb") as file:
                    upload_response = requests.put(upload_url, files={"file": file}, timeout=30)
            except requests.Timeout:
                logger.error(f"Таймаут при загрузке файла {filename}")
                return False
            except requests.RequestException as e:
                logger.error(f"Ошибка запроса при загрузке файла: {e}")
                return False

            if upload_response.status_code == 201:
                logger.info(f"Файл загружен в облако: {filename}")
                return True
            else:
                logger.error(f"Ошибка загрузки файла {filename}: {upload_response.text}")
                return False

        except FileNotFoundError:
            logger.error(f"Файл не найден: {path}")
            return False
        except Exception as e:
            logger.error(f"Неизвестная ошибка при загрузке файла: {e}")
            return False

    def reload(self, path: str) -> bool:
        """
        Перезаписывает файл в облачном хранилище.

        Args:
            path: Путь к файлу на локальном компьютере

        Returns:
            True если перезапись успешна, иначе False
        """
        try:
            filename = os.path.basename(path)
            cloud_path = f"disk:/{self.folder_name}/{filename}"

            logger.info(f"Обновление файла в облаке: {filename} -> {cloud_path}")

            try:
                upload_url_response = requests.get(
                    f"{self.base_url}/resources/upload",
                    headers=self.headers,
                    params={"path": cloud_path, "overwrite": True},
                    timeout=10,
                )
            except requests.Timeout:
                logger.error(f"Таймаут при получении URL для обновления файла {filename}")
                return False
            except requests.RequestException as e:
                logger.error(f"Ошибка запроса при получении URL для обновления: {e}")
                return False

            # Если папка не существует — восстанавливаем её
            if upload_url_response.status_code == 404:
                try:
                    error_data = upload_url_response.json()
                except ValueError:
                    error_data = {}
                if self._is_folder_not_found_error(error_data):
                    logger.warning("Папка в облаке не существует, восстанавливаем...")
                    if self._ensure_folder_exists_silent():
                        try:
                            upload_url_response = requests.get(
                                f"{self.base_url}/resources/upload",
                                headers=self.headers,
                                params={"path": cloud_path, "overwrite": True},
                                timeout=10,
                            )
                        except requests.Timeout:
                            logger.error(
                                f"Таймаут при повторном получении URL для обновления {filename}"
                            )
                            return False
                        except requests.RequestException as e:
                            logger.error(f"Ошибка запроса при повторном получении URL: {e}")
                            return False

            if upload_url_response.status_code != 200:
                logger.error(f"Ошибка получения URL для обновления: {upload_url_response.text}")
                return False

            upload_url = upload_url_response.json().get("href")

            try:
                with open(path, "rb") as file:
                    upload_response = requests.put(upload_url, files={"file": file}, timeout=30)
            except requests.Timeout:
                logger.error(f"Таймаут при обновлении файла {filename}")
                return False
            except requests.RequestException as e:
                logger.error(f"Ошибка запроса при обновлении файла: {e}")
                return False

            if upload_response.status_code == 201:
                logger.info(f"Файл обновлён в облаке: {filename}")
                return True
            else:
                logger.error(f"Ошибка обновления файла {filename}: {upload_response.text}")
                return False

        except FileNotFoundError:
            logger.error(f"Файл не найден: {path}")
            return False
        except Exception as e:
            logger.error(f"Неизвестная ошибка при обновлении файла: {e}")
            return False

    def delete(self, filename: str) -> bool:
        """
        Удаляет файл из облачного хранилища.

        Args:
            filename: Имя файла для удаления

        Returns:
            True если удаление успешно, иначе False
        """
        try:
            cloud_path = f"disk:/{self.folder_name}/{filename}"

            logger.info(f"Удаление файла из облака: {filename} -> {cloud_path}")

            try:
                response = requests.delete(
                    f"{self.base_url}/resources",
                    headers=self.headers,
                    params={"path": cloud_path, "permanently": True},
                    timeout=10,
                )
            except requests.Timeout:
                logger.error(f"Таймаут при удалении файла {filename}")
                return False
            except requests.RequestException as e:
                logger.error(f"Ошибка запроса при удалении файла: {e}")
                return False

            if response.status_code == 204:
                logger.info(f"Файл удалён из облака: {filename}")
                return True
            if response.status_code == 404:
                logger.warning(f"Файл уже отсутствует в облаке: {filename}")
                return True
            else:
                logger.error(f"Ошибка удаления файла {filename}: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Неизвестная ошибка при удалении файла: {e}")
            return False

    def get_info(self) -> Dict[str, str]:
        """
        Получает информацию о файлах в облачном хранилище.

        Returns:
            Словарь {имя_файла: путь_в_облаке}
        """
        try:
            try:
                response = requests.get(
                    f"{self.base_url}/resources",
                    headers=self.headers,
                    params={"path": f"disk:/{self.folder_name}"},
                    timeout=10,
                )
            except requests.Timeout:
                logger.error("Таймаут при получении информации из облака")
                return {}
            except requests.RequestException as e:
                logger.error(f"Ошибка запроса при получении информации: {e}")
                return {}

            # Если папка не существует — восстанавливаем её
            if response.status_code == 404:
                try:
                    error_data = response.json()
                except ValueError:
                    error_data = {}
                if self._is_folder_not_found_error(error_data):
                    logger.warning("Папка в облаке не существует, создаём...")
                    if self._ensure_folder_exists_silent():
                        try:
                            response = requests.get(
                                f"{self.base_url}/resources",
                                headers=self.headers,
                                params={"path": f"disk:/{self.folder_name}"},
                                timeout=10,
                            )
                        except requests.Timeout:
                            logger.error("Таймаут при повторном получении информации из облака")
                            return {}
                        except requests.RequestException as e:
                            logger.error(f"Ошибка запроса при повторном получении информации: {e}")
                            return {}

            if response.status_code != 200:
                logger.error(f"Ошибка получения информации из облака: {response.text}")
                return {}

            try:
                data = response.json()
            except ValueError:
                logger.error("Ошибка парсинга ответа от облака")
                return {}

            files_info = {}

            for item in data.get("_embedded", {}).get("items", []):
                if item.get("type") == "file":
                    files_info[item.get("name")] = item.get("path")

            return files_info

        except Exception as e:
            logger.error(f"Неизвестная ошибка при получении информации: {e}")
            return {}
