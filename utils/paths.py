import os
import sys


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

    def get_path(self, *relative_paths):
        """Получить абсолютный путь к ресурсу"""
        return os.path.join(self.resources_dir, *relative_paths)

    def get_executable_dir_path(self, *relative_paths):
        """Получить путь относительно директории исполняемого файла"""
        return os.path.join(self.executable_dir, *relative_paths)

pm = PathManager()