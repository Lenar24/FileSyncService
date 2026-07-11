"""Тесты для модуля cloud_storage.py."""

from unittest.mock import MagicMock

import pytest
import requests

from cloud_storage import CloudStorage


class TestCloudStorage:
    """Тесты для класса CloudStorage."""

    def test_init_valid_token(self, mocker):
        """Тест: успешная инициализация с валидным токеном."""
        mock_get = mocker.patch("requests.get")

        responses = [
            MagicMock(status_code=200),  # проверка токена
            MagicMock(status_code=200),  # проверка папки
        ]
        mock_get.side_effect = responses

        cloud = CloudStorage(token="valid_token", folder_name="TestFolder")

        assert cloud.token == "valid_token"
        assert cloud.folder_name == "TestFolder"
        assert cloud.base_url == "https://cloud-api.yandex.net/v1/disk"
        assert cloud.headers["Authorization"] == "OAuth valid_token"

    def test_init_invalid_token(self, mocker):
        """Тест: ошибка при невалидном токене."""
        mock_get = mocker.patch("requests.get")
        mock_get.return_value.status_code = 401

        with pytest.raises(ValueError, match="Неверный токен доступа"):
            CloudStorage(token="invalid_token", folder_name="TestFolder")

    def test_init_folder_creation(self, mocker):
        """Тест: создание папки, если её нет."""
        mock_get = mocker.patch("requests.get")
        mock_put = mocker.patch("requests.put")

        responses = [
            MagicMock(status_code=200),  # проверка токена
            MagicMock(status_code=404),  # проверка папки
        ]
        mock_get.side_effect = responses
        mock_put.return_value.status_code = 201

        CloudStorage(token="valid_token", folder_name="NewFolder")

        mock_put.assert_called_once()
        call_args = mock_put.call_args[1]
        assert "params" in call_args
        assert call_args["params"]["path"] == "disk:/NewFolder"

    def test_load_success(self, mocker, tmp_path):
        """Тест: успешная загрузка файла."""
        mock_get = mocker.patch("requests.get")
        mock_put = mocker.patch("requests.put")

        call_count = 0

        def get_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            response = MagicMock()

            # Проверка токена или папки
            if call_count <= 2:
                response.status_code = 200
                return response

            # Запрос на получение URL для загрузки
            if "/resources/upload" in args[0]:
                response.status_code = 200
                response.json.return_value = {"href": "https://upload.url"}
                return response

            response.status_code = 200
            return response

        mock_get.side_effect = get_side_effect
        mock_put.return_value.status_code = 201

        cloud = CloudStorage(token="valid_token", folder_name="TestFolder")

        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, Cloud!")

        result = cloud.load(str(test_file))

        assert result is True
        mock_put.assert_called_once()

    def test_load_file_not_found(self, mocker):
        """Тест: ошибка при отсутствии файла."""
        mock_get = mocker.patch("requests.get")
        mock_get.return_value.status_code = 200

        cloud = CloudStorage(token="valid_token", folder_name="TestFolder")

        result = cloud.load("/nonexistent/file.txt")

        assert result is False

    def test_load_network_error(self, mocker):
        """Тест: ошибка сети при загрузке."""
        mock_get = mocker.patch("requests.get")

        call_count = 0

        def get_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            # Первые два вызова — проверка токена и папки (успех)
            if call_count <= 2:
                response = MagicMock()
                response.status_code = 200
                return response

            # Третий вызов — получение URL для загрузки (ошибка)
            if "/resources/upload" in args[0]:
                raise requests.RequestException("Network error")

            response = MagicMock()
            response.status_code = 200
            return response

        mock_get.side_effect = get_side_effect

        cloud = CloudStorage(token="valid_token", folder_name="TestFolder")

        result = cloud.load("/some/file.txt")

        assert result is False

    def test_reload_success(self, mocker, tmp_path):
        """Тест: успешное обновление файла."""
        mock_get = mocker.patch("requests.get")
        mock_put = mocker.patch("requests.put")

        call_count = 0

        def get_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            response = MagicMock()

            if call_count <= 2:
                response.status_code = 200
                return response

            if "/resources/upload" in args[0]:
                response.status_code = 200
                response.json.return_value = {"href": "https://upload.url"}
                return response

            response.status_code = 200
            return response

        mock_get.side_effect = get_side_effect
        mock_put.return_value.status_code = 201

        cloud = CloudStorage(token="valid_token", folder_name="TestFolder")

        test_file = tmp_path / "test.txt"
        test_file.write_text("Updated content")

        result = cloud.reload(str(test_file))

        assert result is True
        mock_put.assert_called_once()

    def test_delete_success(self, mocker):
        """Тест: успешное удаление файла."""
        mock_get = mocker.patch("requests.get")
        mock_delete = mocker.patch("requests.delete")

        mock_get.return_value.status_code = 200
        mock_delete.return_value.status_code = 204

        cloud = CloudStorage(token="valid_token", folder_name="TestFolder")

        result = cloud.delete("test.txt")

        assert result is True
        mock_delete.assert_called_once()

    def test_delete_file_not_found(self, mocker):
        """Тест: удаление уже отсутствующего файла."""
        mock_get = mocker.patch("requests.get")
        mock_delete = mocker.patch("requests.delete")

        mock_get.return_value.status_code = 200
        mock_delete.return_value.status_code = 404

        cloud = CloudStorage(token="valid_token", folder_name="TestFolder")

        result = cloud.delete("nonexistent.txt")

        assert result is True

    def test_get_info_success(self, mocker):
        """Тест: получение информации о файлах."""
        mock_get = mocker.patch("requests.get")

        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "_embedded": {
                "items": [
                    {
                        "name": "file1.txt",
                        "type": "file",
                        "path": "disk:/path/file1.txt",
                    },
                    {
                        "name": "file2.txt",
                        "type": "file",
                        "path": "disk:/path/file2.txt",
                    },
                    {"name": "folder", "type": "dir", "path": "disk:/path/folder"},
                ]
            }
        }

        cloud = CloudStorage(token="valid_token", folder_name="TestFolder")

        result = cloud.get_info()

        assert "file1.txt" in result
        assert "file2.txt" in result
        assert "folder" not in result
        assert result["file1.txt"] == "disk:/path/file1.txt"

    def test_get_info_network_error(self, mocker):
        """Тест: ошибка сети при получении информации."""
        mock_get = mocker.patch("requests.get")

        call_count = 0

        def get_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            # Первый вызов — проверка токена (успех)
            if call_count == 1:
                response = MagicMock()
                response.status_code = 200
                return response

            # Второй вызов — проверка папки (успех)
            elif call_count == 2:
                response = MagicMock()
                response.status_code = 200
                response.json.return_value = {"_embedded": {"items": []}}
                return response

            # Третий вызов — получение информации о файлах (ошибка сети)
            else:
                raise requests.RequestException("Network error")

        mock_get.side_effect = get_side_effect

        cloud = CloudStorage(token="valid_token", folder_name="TestFolder")

        result = cloud.get_info()

        assert result == {}
