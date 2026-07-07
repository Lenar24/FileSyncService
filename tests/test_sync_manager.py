"""Тесты для модуля sync_manager.py."""

import os
import time

import pytest

from sync_manager import SyncManager


class TestSyncManager:
    """Тесты для класса SyncManager."""

    def test_init_success(self, sync_folder, cloud_storage_mock):
        """Тест: успешная инициализация менеджера."""
        manager = SyncManager(sync_folder, cloud_storage_mock)

        assert manager.sync_folder == sync_folder
        assert manager.cloud == cloud_storage_mock
        assert manager.file_states == {}
        assert manager.first_sync_done is False

    def test_init_folder_not_exists(self, cloud_storage_mock):
        """Тест: ошибка при отсутствии папки."""
        with pytest.raises(ValueError, match="Синхронизируемая папка не существует"):
            SyncManager("/nonexistent/path", cloud_storage_mock)

    def test_get_local_files(self, sync_folder, cloud_storage_mock):
        """Тест: получение списка локальных файлов."""
        with open(os.path.join(sync_folder, "file1.txt"), "w") as f:
            f.write("test")
        with open(os.path.join(sync_folder, "file2.txt"), "w") as f:
            f.write("test")

        manager = SyncManager(sync_folder, cloud_storage_mock)
        files = manager._get_local_files()

        assert "file1.txt" in files
        assert "file2.txt" in files
        assert len(files) == 2

    def test_full_sync_new_file(self, sync_folder, cloud_storage_mock):
        """Тест: полная синхронизация — новый файл загружается."""
        manager = SyncManager(sync_folder, cloud_storage_mock)

        filepath = os.path.join(sync_folder, "new.txt")
        with open(filepath, "w") as f:
            f.write("New file")

        cloud_storage_mock.get_info.return_value = {}

        manager._full_sync()

        cloud_storage_mock.load.assert_called_once_with(filepath)
        assert "new.txt" in manager.file_states

    def test_full_sync_modified_file(self, sync_folder, cloud_storage_mock):
        """Тест: полная синхронизация — изменённый файл обновляется."""
        manager = SyncManager(sync_folder, cloud_storage_mock)

        filepath = os.path.join(sync_folder, "existing.txt")
        with open(filepath, "w") as f:
            f.write("Initial content")

        initial_mtime = os.path.getmtime(filepath)
        manager.file_states["existing.txt"] = initial_mtime

        cloud_storage_mock.get_info.return_value = {"existing.txt": "disk:/path/existing.txt"}

        time.sleep(0.1)
        with open(filepath, "w") as f:
            f.write("Updated content")

        manager._full_sync()

        cloud_storage_mock.reload.assert_called_once_with(filepath)
        assert manager.file_states["existing.txt"] > initial_mtime

    def test_full_sync_deleted_file(self, sync_folder, cloud_storage_mock):
        """Тест: полная синхронизация — удалённый файл удаляется из облака."""
        manager = SyncManager(sync_folder, cloud_storage_mock)

        manager.file_states["deleted.txt"] = 1234567890.0
        cloud_storage_mock.get_info.return_value = {"deleted.txt": "disk:/path/deleted.txt"}

        manager._full_sync()

        cloud_storage_mock.delete.assert_called_once_with("deleted.txt")
        assert "deleted.txt" not in manager.file_states

    def test_sync_once_first_full_sync(self, sync_folder, cloud_storage_mock):
        """Тест: первый вызов sync_once выполняет полную синхронизацию."""
        manager = SyncManager(sync_folder, cloud_storage_mock)

        filepath = os.path.join(sync_folder, "file.txt")
        with open(filepath, "w") as f:
            f.write("test")

        cloud_storage_mock.get_info.return_value = {}

        manager.sync_once()

        cloud_storage_mock.load.assert_called_once()
        assert manager.first_sync_done is True

    def test_sync_once_new_file(self, sync_folder, cloud_storage_mock):
        """Тест: обнаружение нового файла."""
        manager = SyncManager(sync_folder, cloud_storage_mock)
        manager.first_sync_done = True

        filepath = os.path.join(sync_folder, "new.txt")
        with open(filepath, "w") as f:
            f.write("New file")

        cloud_storage_mock.get_info.return_value = {}

        manager.sync_once()

        cloud_storage_mock.load.assert_called_once_with(filepath)
        assert "new.txt" in manager.file_states

    def test_sync_once_modified_file(self, sync_folder, cloud_storage_mock):
        """Тест: обнаружение изменённого файла."""
        manager = SyncManager(sync_folder, cloud_storage_mock)

        filepath = os.path.join(sync_folder, "file.txt")
        with open(filepath, "w") as f:
            f.write("Initial")
        manager.file_states["file.txt"] = os.path.getmtime(filepath)
        manager.first_sync_done = True

        cloud_storage_mock.get_info.return_value = {"file.txt": "disk:/path/file.txt"}

        time.sleep(0.1)
        with open(filepath, "w") as f:
            f.write("Updated")

        manager.sync_once()

        cloud_storage_mock.reload.assert_called_once_with(filepath)

    def test_sync_once_deleted_file(self, sync_folder, cloud_storage_mock):
        """Тест: обнаружение удалённого файла."""
        manager = SyncManager(sync_folder, cloud_storage_mock)

        manager.file_states["deleted.txt"] = 1234567890.0
        manager.first_sync_done = True

        cloud_storage_mock.get_info.return_value = {"deleted.txt": "disk:/path/deleted.txt"}

        manager.sync_once()

        cloud_storage_mock.delete.assert_called_once_with("deleted.txt")
        assert "deleted.txt" not in manager.file_states

    def test_sync_once_cloud_files(self, sync_folder, cloud_storage_mock):
        """Тест: учёт файлов из облака при синхронизации."""
        manager = SyncManager(sync_folder, cloud_storage_mock)
        manager.first_sync_done = True

        filepath = os.path.join(sync_folder, "local.txt")
        with open(filepath, "w") as f:
            f.write("Local file")

        cloud_storage_mock.get_info.return_value = {"cloud_only.txt": "disk:/path/cloud_only.txt"}
        cloud_storage_mock.load.return_value = True
        cloud_storage_mock.delete.return_value = True

        manager.sync_once()

        cloud_storage_mock.load.assert_called_once_with(filepath)
        cloud_storage_mock.delete.assert_called_once_with("cloud_only.txt")

    def test_sync_once_error_handling(self, sync_folder, cloud_storage_mock):
        """Тест: ошибки не прерывают работу."""
        manager = SyncManager(sync_folder, cloud_storage_mock)
        manager.first_sync_done = True

        cloud_storage_mock.get_info.side_effect = Exception("Test error")

        # Не должно выбросить исключение
        manager.sync_once()

        assert True


class TestSyncManagerRecovery:
    """Тесты для сценариев восстановления."""

    def test_ensure_cloud_consistency_empty_folder(self, sync_folder, cloud_storage_mock):
        """Тест: проверка согласованности — облачная папка пуста."""
        manager = SyncManager(sync_folder, cloud_storage_mock)
        manager.first_sync_done = True

        filepath = os.path.join(sync_folder, "test.txt")
        with open(filepath, "w") as f:
            f.write("Local file")

        cloud_storage_mock.get_info.return_value = {}
        cloud_storage_mock.load.return_value = True

        manager._ensure_cloud_consistency()

        cloud_storage_mock.load.assert_called_once_with(filepath)
        assert "test.txt" in manager.file_states

    def test_sync_once_recovers_deleted_folder(self, sync_folder, cloud_storage_mock):
        """Тест: sync_once восстанавливает удалённую папку."""
        manager = SyncManager(sync_folder, cloud_storage_mock)
        manager.first_sync_done = True

        filepath = os.path.join(sync_folder, "test.txt")
        with open(filepath, "w") as f:
            f.write("Local file")

        cloud_storage_mock.get_info.return_value = {}
        cloud_storage_mock.load.return_value = True

        manager.sync_once()

        cloud_storage_mock.load.assert_called_once_with(filepath)
        assert "test.txt" in manager.file_states

    def test_full_recovery_scenario(self, sync_folder, cloud_storage_mock):
        """Тест: полный сценарий восстановления после удаления папки."""
        manager = SyncManager(sync_folder, cloud_storage_mock)

        file1 = os.path.join(sync_folder, "file1.txt")
        file2 = os.path.join(sync_folder, "file2.txt")
        with open(file1, "w") as f:
            f.write("Content 1")
        with open(file2, "w") as f:
            f.write("Content 2")

        cloud_storage_mock.get_info.return_value = {}
        cloud_storage_mock.load.return_value = True

        manager.sync_once()

        assert cloud_storage_mock.load.call_count == 2
        assert manager.first_sync_done is True

        cloud_storage_mock.load.reset_mock()
        cloud_storage_mock.get_info.return_value = {}

        manager.sync_once()

        assert cloud_storage_mock.load.call_count == 2
        assert "file1.txt" in manager.file_states
        assert "file2.txt" in manager.file_states
