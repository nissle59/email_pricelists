import io
import sys
import threading
from tkinter import scrolledtext

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from contextlib import redirect_stdout, redirect_stderr


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

    def redirect_output(self):
        """Перенаправляет stdout и stderr в текстовое поле"""

        class TextRedirector(io.TextIOBase):
            def __init__(self, widget, tag="stdout"):
                self.is_running = None
                self.widget = widget
                self.tag = tag

            def write(self, text):
                if not self.is_running:
                    return
                self.widget.insert(END, text)
                self.widget.see(END)
                self.widget.update_idletasks()

            def flush(self):
                pass

        sys.stdout = TextRedirector(self.text_area, "stdout")
        sys.stderr = TextRedirector(self.text_area, "stderr")

    def restore_output(self):
        """Восстанавливает стандартные потоки вывода"""
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__

    def run_task(self, task_function, *args, **kwargs):
        """Запускает задачу в отдельном потоке"""
        self.redirect_output()
        self.thread = threading.Thread(
            target=self._execute_task,
            args=(task_function, args, kwargs)
        )
        self.thread.daemon = True
        self.thread.start()

        # Проверяем завершение потока
        self._check_thread()

    def _execute_task(self, task_function, args, kwargs):
        """Выполняет задачу и перехватывает исключения"""
        try:
            task_function(*args, **kwargs)
        except Exception as e:
            print(f"Ошибка при выполнении задачи: {e}")
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
        self.is_running = False
        self.restore_output()
        self.window.destroy()


class SimpleConsoleWindow:
    def __init__(self, task_function, *args, **kwargs):
        self.window = ttk.Toplevel(None)
        self.window.title("Выполнение задачи")
        self.window.geometry("600x400")

        self.text_area = scrolledtext.ScrolledText(self.window)
        self.text_area.pack(fill=BOTH, expand=True, padx=10, pady=10)

        self.task_function = task_function
        self.args = args
        self.kwargs = kwargs

        # Запускаем задачу
        self.start_task()

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
            except Exception as e:
                self.output_buffer.write(f"Ошибка: {e}\n")
            finally:
                self.task_completed = True

        self.task_completed = False
        self.thread = threading.Thread(target=run_in_thread)
        self.thread.daemon = True
        self.thread.start()

        # Запускаем обновление вывода
        self.update_output()

    def update_output(self):
        """Обновляет вывод в текстовом поле"""
        # Получаем весь вывод из буфера
        output = self.output_buffer.getvalue()
        if output:
            # Очищаем буфер после чтения
            self.output_buffer.truncate(0)
            self.output_buffer.seek(0)

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
                self.text_area.insert(END, final_output)
                self.text_area.see(END)
            self.window.after(1000, self.window.destroy)  # Закрываем через 1 секунду