import io
import sys
import threading
from tkinter import scrolledtext
from pathlib import Path
from datetime import datetime
import logging

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from contextlib import redirect_stdout, redirect_stderr

from utils.paths import pm


class ConsoleWindow:
    def __init__(self, parent):
        self.window = ttk.Toplevel(parent)
        self.window.title("Выполнение задачи")
        self.window.geometry("600x400")

        # Текстовое поле для вывода
        self.text_area = scrolledtext.ScrolledText(
            self.window,
            wrap=WORD,
            width=70,
            height=20
        )
        self.text_area.pack(padx=10, pady=10, fill=BOTH, expand=True)

        # Кнопка отмены
        self.cancel_button = ttk.Button(
            self.window,
            text="Отмена",
            command=self.cancel
        )
        self.cancel_button.pack(pady=5)

        self.is_running = True
        self.thread = None
        self.logger = None

    def setup_logging(self, function_name):
        """Настраивает логирование в файл"""
        log_path = Path(pm.get_logs()) / f"{function_name}.log"

        # Создаем логгер
        self.logger = logging.getLogger(function_name)
        self.logger.setLevel(logging.INFO)

        # Очищаем предыдущие обработчики
        self.logger.handlers.clear()

        # Создаем обработчик для файла
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.INFO)

        # Форматирование с временными метками
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)

        return self.logger

    def redirect_output(self, function_name):
        """Перенаправляет stdout и stderr в текстовое поле и файл"""
        self.setup_logging(function_name)

        class TextRedirector(io.TextIOBase):
            def __init__(self, widget, logger, tag="stdout"):
                self.widget = widget
                self.logger = logger
                self.tag = tag
                self.is_running = True
                self.buffer = ""

            def write(self, text):
                if not self.is_running:
                    return

                # Добавляем в буфер
                self.buffer += text

                # Если есть полная строка (заканчивается переводом строки)
                if '\n' in self.buffer:
                    lines = self.buffer.split('\n')
                    # Обрабатываем все полные строки
                    for line in lines[:-1]:
                        if line.strip():  # Игнорируем пустые строки
                            # Логируем с временной меткой
                            if self.tag == "stderr":
                                self.logger.error(line)
                            else:
                                self.logger.info(line)

                            # Выводим в текстовое поле
                            self.widget.insert(END, line + '\n')
                            self.widget.see(END)

                    # Оставляем неполную строку в буфере
                    self.buffer = lines[-1]

                self.widget.update_idletasks()

            def flush(self):
                # Обрабатываем оставшиеся данные в буфере
                if self.buffer.strip():
                    if self.tag == "stderr":
                        self.logger.error(self.buffer)
                    else:
                        self.logger.info(self.buffer)

                    self.widget.insert(END, self.buffer)
                    self.widget.see(END)
                    self.buffer = ""
                self.widget.update_idletasks()

        sys.stdout = TextRedirector(self.text_area, self.logger, "stdout")
        sys.stderr = TextRedirector(self.text_area, self.logger, "stderr")

    def restore_output(self):
        """Восстанавливает стандартные потоки вывода"""
        # Обрабатываем оставшиеся данные перед восстановлением
        if hasattr(sys.stdout, 'flush'):
            sys.stdout.flush()
        if hasattr(sys.stderr, 'flush'):
            sys.stderr.flush()

        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

        # Закрываем обработчики логгера
        if self.logger:
            for handler in self.logger.handlers:
                handler.close()
            self.logger.handlers.clear()

    def run_task(self, task_function, *args, **kwargs):
        """Запускает задачу в отдельном потоке"""
        function_name = task_function.__name__
        self.redirect_output(function_name)

        # Логируем начало выполнения
        self.logger.info(f"Начало выполнения функции: {function_name}")

        self.thread = threading.Thread(
            target=self._execute_task,
            args=(task_function, args, kwargs, function_name)
        )
        self.thread.daemon = True
        self.thread.start()

        # Проверяем завершение потока
        self._check_thread()

    def _execute_task(self, task_function, args, kwargs, function_name):
        """Выполняет задачу и перехватывает исключения"""
        try:
            task_function(*args, **kwargs)
            # Логируем успешное завершение
            if self.logger:
                self.logger.info(f"Функция {function_name} выполнена успешно")
        except Exception as e:
            error_msg = f"Ошибка при выполнении задачи {function_name}: {e}"
            print(error_msg)
            if self.logger:
                self.logger.error(error_msg)
        finally:
            self.is_running = False

    def _check_thread(self):
        """Проверяет статус выполнения потока"""
        if self.thread.is_alive():
            # Поток еще работает, проверяем снова через 100мс
            self.window.after(100, self._check_thread)
        else:
            # Задача завершена, закрываем окно
            self.restore_output()
            self.window.destroy()

    def cancel(self):
        """Отменяет выполнение задачи"""
        if self.logger:
            self.logger.warning("Выполнение задачи отменено пользователем")
        self.is_running = False
        self.restore_output()
        self.window.destroy()


class SimpleConsoleWindow:
    def __init__(self, task_function, *args, **kwargs):
        self.window = ttk.Toplevel(None)
        self.window.title("Выполнение задачи")
        self.window.geometry("1000x400")

        self.text_area = scrolledtext.ScrolledText(self.window)
        self.text_area.pack(fill=BOTH, expand=True, padx=10, pady=10)

        self.task_function = task_function
        self.args = args
        self.kwargs = kwargs
        self.function_name = task_function.__name__

        # Настраиваем логирование
        self.setup_logging()

        # Запускаем задачу
        self.start_task()

    def setup_logging(self):
        """Настраивает логирование в файл"""
        log_path = Path(pm.get_logs()) / f"{self.function_name}.log"

        # Создаем логгер
        self.logger = logging.getLogger(self.function_name)
        self.logger.setLevel(logging.INFO)

        # Очищаем предыдущие обработчики
        self.logger.handlers.clear()

        # Создаем обработчик для файла
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.INFO)

        # Форматирование с временными метками
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)

        # Логируем начало выполнения
        self.logger.info(f"Начало выполнения функции: {self.function_name}")

    def log_message(self, message, level='info'):
        """Логирует сообщение с указанным уровнем"""
        if self.logger:
            if level == 'error':
                self.logger.error(message)
            elif level == 'warning':
                self.logger.warning(message)
            else:
                self.logger.info(message)

    def start_task(self):
        """Запускает задачу с перенаправлением вывода"""
        import io
        from contextlib import redirect_stdout, redirect_stderr

        # Создаем буфер для вывода
        self.output_buffer = io.StringIO()

        def run_in_thread():
            """Выполняет задачу в потоке с перехватом вывода"""
            try:
                with redirect_stdout(self.output_buffer), redirect_stderr(self.output_buffer):
                    self.task_function(*self.args, **self.kwargs)
                self.log_message(f"Функция {self.function_name} выполнена успешно")
            except Exception as e:
                error_msg = f"Ошибка при выполнении задачи: {e}"
                self.output_buffer.write(error_msg + "\n")
                self.log_message(error_msg, 'error')
            finally:
                self.task_completed = True

        self.task_completed = False
        self.thread = threading.Thread(target=run_in_thread)
        self.thread.daemon = True
        self.thread.start()

        # Запускаем обновление вывода
        self.update_output()

    def update_output(self):
        """Обновляет вывод в текстовом поле и логирует его"""
        # Получаем весь вывод из буфера
        output = self.output_buffer.getvalue()
        if output:
            # Очищаем буфер после чтения
            self.output_buffer.truncate(0)
            self.output_buffer.seek(0)

            # Логируем вывод
            for line in output.splitlines():
                if line.strip():  # Игнорируем пустые строки
                    self.log_message(line)

            # Обновляем текстовое поле
            self.text_area.insert(END, output)
            self.text_area.see(END)

        # Проверяем, завершена ли задача
        if self.thread.is_alive():
            # Если нет, продолжаем обновление
            self.window.after(100, self.update_output)
        else:
            # Если да, выводим оставшийся вывод и закрываем окно
            final_output = self.output_buffer.getvalue()
            if final_output:
                # Логируем оставшийся вывод
                for line in final_output.splitlines():
                    if line.strip():
                        self.log_message(line)

                self.text_area.insert(END, final_output)
                self.text_area.see(END)

            # Закрываем обработчики логгера
            if self.logger:
                for handler in self.logger.handlers:
                    handler.close()
                self.logger.handlers.clear()

            self.window.after(1000, self.window.destroy)  # Закрываем через 1 секунду