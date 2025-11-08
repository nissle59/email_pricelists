import os
import sys
from pathlib import Path
from typing import Literal
import appdirs


class PathManager:
    def __init__(self):
        self.is_frozen = getattr(sys, 'frozen', False)
        self._setup_paths()

    def _setup_paths(self):
        if self.is_frozen:
            # Исполняемый режим
            self.executable_dir = os.path.dirname(sys.executable)
            self.resources_dir = getattr(sys, '_MEIPASS', self.executable_dir)
            # Устанавливаем рабочую директорию
            os.chdir(self.executable_dir)
        else:
            # Режим разработки
            self.executable_dir = os.path.dirname(os.path.abspath(__file__))
            self.resources_dir = self.executable_dir

    def get_save_directory(self, mode: Literal['main', 'source', 'parsed'] = 'main'):
        """Определяет правильную директорию для сохранения файлов"""
        # if getattr(sys, 'frozen', False):
        # Если приложение собрано в .app
        desktop_path = Path.home() / 'Desktop'
        app_folder = desktop_path / 'Pricelist_Files'
        if mode == 'source':
            app_folder = app_folder / 'Оригиналы прайсов'
        elif mode == 'parsed':
            app_folder = app_folder / 'Обработанные прайсы'
        app_folder.mkdir(exist_ok=True, parents=True)
        return str(app_folder)
        # else:
        #     # При разработке - сохраняем рядом со скриптом
        #     return os.path.dirname(os.path.abspath(__file__))

    def save_file(self, filename, mode: Literal['main', 'source', 'parsed'] = 'main'):
        save_dir = self.get_save_directory(mode)
        filepath = os.path.join(save_dir, filename)

        # Ваш код сохранения файла
        # data.to_excel(filepath)  # для pandas
        # или другой метод сохранения

        return filepath

    def get_path(self, *relative_paths):
        """Получить абсолютный путь к ресурсу"""
        return os.path.join(self.resources_dir, *relative_paths)

    def get_executable_dir_path(self, *relative_paths):
        """Получить путь относительно директории исполняемого файла"""
        return os.path.join(self.executable_dir, *relative_paths)

    def get_app_dirs_standard(self):
        """Использует библиотеку appdirs для стандартных путей"""
        app_name = "Pricelist"
        app_author = "Nissle"

        return {
            'user_data': Path(appdirs.user_data_dir(app_name, app_author)),
            'user_config': Path(appdirs.user_config_dir(app_name, app_author)),
            'user_cache': Path(appdirs.user_cache_dir(app_name, app_author)),
            'user_logs': Path(appdirs.user_log_dir(app_name, app_author)),
            'site_data': Path(appdirs.site_data_dir(app_name, app_author)),
        }

    def get_user_data(self):
        ud = self.get_app_dirs_standard()['user_data'].mkdir(parents=True, exist_ok=True)
        return self.get_app_dirs_standard()['user_data']

pm = PathManager()