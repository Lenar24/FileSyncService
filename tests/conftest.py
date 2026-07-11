"""Фикстуры для тестов."""

import os
import tempfile
from typing import Generator

import pytest

from cloud_storage import CloudStorage
from sync_manager import SyncManager


@pytest.fixture
def temp_folder() -> Generator[str, None, None]:
    """Создаёт временную папку для тестов."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sync_folder(temp_folder: str) -> str:
    """Создаёт папку для синхронизации внутри временной папки."""
    folder = os.path.join(temp_folder, "sync_folder")
    os.makedirs(folder)
    return folder


@pytest.fixture
def cloud_storage_mock(mocker):
    """Создаёт мок для CloudStorage."""
    mock = mocker.MagicMock(spec=CloudStorage)
    mock.get_info.return_value = {}
    mock.load.return_value = True
    mock.reload.return_value = True
    mock.delete.return_value = True
    return mock


@pytest.fixture
def sync_manager(sync_folder: str, cloud_storage_mock) -> SyncManager:
    """Создаёт экземпляр SyncManager с моком облачного хранилища."""
    manager = SyncManager(sync_folder, cloud_storage_mock)
    manager.first_sync_done = False
    return manager


@pytest.fixture
def sample_file(sync_folder: str) -> str:
    """Создаёт тестовый файл в папке синхронизации."""
    filepath = os.path.join(sync_folder, "test.txt")
    with open(filepath, "w") as f:
        f.write("Hello, World!")
    return filepath


@pytest.fixture
def mock_requests(mocker):
    """Мок для requests.get и requests.put."""
    mock_get = mocker.patch("requests.get")
    mock_put = mocker.patch("requests.put")
    mock_delete = mocker.patch("requests.delete")

    # Настройка стандартных ответов
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"href": "https://upload.url"}

    mock_put.return_value.status_code = 201

    mock_delete.return_value.status_code = 204

    return {"get": mock_get, "put": mock_put, "delete": mock_delete}


@pytest.fixture
def cloud_storage_real(mock_requests) -> CloudStorage:
    """Создаёт реальный экземпляр CloudStorage с мокнутыми запросами."""
    return CloudStorage(token="fake_token", folder_name="TestFolder")
