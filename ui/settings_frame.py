from typing import Self, TYPE_CHECKING
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.toast import ToastNotification
from ttkbootstrap.scrolled import ScrolledFrame
import json

import crud
from models import Filters
from settings import settings
from ui.parser_config_dialog import ParserConfigWindow
from ya_client import client as email_client

if TYPE_CHECKING:
    from ui.gui import App


class EmailSettingsFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill=BOTH, expand=YES, padx=10, pady=10)
        self._create_widgets()

    def _create_widgets(self):
        # Заголовок
        ttk.Label(
            self,
            text="Настройки подключения к почте",
            font=("Helvetica", 14, "bold")
        ).pack(anchor=W, pady=(0, 15))

        # Основной контейнер
        container = ttk.Frame(self)
        container.pack(fill=X, padx=5)

        # Логин (email)
        ttk.Label(container, text="Логин (email):", width=20).grid(row=0, column=0, sticky=W, pady=5)
        self.email_var = ttk.StringVar(value=settings.get('email_username'))
        email_entry = ttk.Entry(container, textvariable=self.email_var, width=30)
        email_entry.grid(row=0, column=1, sticky=W, pady=5, padx=(0, 10))

        # Пароль
        ttk.Label(container, text="Пароль:", width=20).grid(row=1, column=0, sticky=W, pady=5)
        self.password_var = ttk.StringVar(value=settings.get('email_password'))
        password_entry = ttk.Entry(container, textvariable=self.password_var, show="*", width=30)
        password_entry.grid(row=1, column=1, sticky=W, pady=5, padx=(0, 10))

        # IMAP сервер
        ttk.Label(container, text="IMAP сервер:", width=20).grid(row=2, column=0, sticky=W, pady=5)
        self.imap_var = ttk.StringVar(value=settings.get('email_server'))
        imap_entry = ttk.Entry(container, textvariable=self.imap_var, width=30)
        imap_entry.grid(row=2, column=1, sticky=W, pady=5, padx=(0, 10))

        # Порт
        ttk.Label(container, text="Порт:", width=20).grid(row=3, column=0, sticky=W, pady=5)
        self.port_var = ttk.StringVar(value=settings.get('email_port'))
        port_entry = ttk.Entry(container, textvariable=self.port_var, width=30)
        port_entry.grid(row=3, column=1, sticky=W, pady=5, padx=(0, 10))

        # Кнопки
        btn_frame = ttk.Frame(container)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=15, sticky=W)

        ttk.Button(
            btn_frame,
            text="Сохранить настройки",
            bootstyle=SUCCESS,
            command=self._save_email_settings
        ).pack(side=LEFT, padx=(0, 10))

        ttk.Button(
            btn_frame,
            text="Проверить подключение",
            bootstyle=INFO,
            command=self._test_connection
        ).pack(side=LEFT)

    def _save_email_settings(self):
        s = {
            'email_username': self.email_var.get(),
            'email_password': self.password_var.get(),
            'email_server': self.imap_var.get(),
            'email_port': self.port_var.get()
        }
        crud.set_settings(s)
        ToastNotification(
            title="Сохранено",
            message="Настройки почты сохранены",
            bootstyle=SUCCESS
        ).show_toast()

    def _test_connection(self):
        # Здесь будет тестирование подключения
        client = email_client
        client.set_credentials(self.email_var.get(), self.password_var.get(), self.imap_var.get(),
                               int(self.port_var.get()))
        try:
            conn_res = client.connect()
            if conn_res == 1:
                ToastNotification(
                    title="Проверка подключения",
                    message="Успешное подключение",
                    bootstyle=SUCCESS
                ).show_toast()
            else:
                ToastNotification(
                    title="Проверка подключения",
                    message="Подключение не удалось",
                    bootstyle=DANGER
                ).show_toast()
        except Exception as e:
            ToastNotification(
                title="Проверка подключения",
                message="Подключение не удалось",
                bootstyle=DANGER
            ).show_toast()
        finally:
            client.disconnect()


class FilterRuleRow(ttk.Frame):
    def __init__(self, parent, rule_data=None, on_delete=None):
        super().__init__(parent)
        if rule_data:
            self.rd_raw: Filters = rule_data
            self.rule_data = rule_data.as_dict() or {}
        else:
            self.rd_raw = None
            self.rule_data = {}
        self.on_delete = on_delete
        self._create_widgets()

    def _create_widgets(self):
        # Переменные для полей ввода
        self.name_var = ttk.StringVar(value=self.rule_data.get('name', ''))
        self.sender_var = ttk.StringVar(value=self.rule_data.get('senders', ''))
        self.subject_contains_var = ttk.StringVar(value=self.rule_data.get('subject_contains', ''))
        self.subject_excludes_var = ttk.StringVar(value=self.rule_data.get('subject_excludes', ''))
        self.extensions_var = ttk.StringVar(value=self.rule_data.get('extensions', ''))
        self.filename_contains_var = ttk.StringVar(value=self.rule_data.get('filename_contains', ''))
        self.filename_excludes_var = ttk.StringVar(value=self.rule_data.get('filename_excludes', ''))
        self.accept_all_var = ttk.BooleanVar(value=self.rule_data.get('accept_all', False))

        def on_focus_out(event):
            new_name = self.name_var.get()
            if self.rd_raw:
                filter_id = self.rd_raw.id
                if self.rd_raw.name != new_name:
                    self.rd_raw.name = new_name
                    crud.update_email_filter(filter_id, self.rd_raw)
                    print(f"Ввод завершен: {self.name_var.get()}")
            else:
                self.rd_raw = crud.add_email_filter(Filters(name=new_name))

        # Поля ввода
        name_entry = ttk.Entry(self, textvariable=self.name_var, width=15)
        name_entry.grid(row=0, column=0, padx=2, pady=2, sticky=EW)
        name_entry.bind('<FocusOut>', on_focus_out)

        # Кнопки действий
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=0, column=1, padx=2, pady=2, sticky=W)

        ttk.Button(
            btn_frame,
            text="Парсер",
            bootstyle=SECONDARY,
            command=self._configure_parser,
            width=8
        ).pack(side=LEFT, padx=(0, 2))

        ttk.Button(
            btn_frame,
            text="Удалить",
            bootstyle=DANGER,
            command=self._delete_rule,
            width=8
        ).pack(side=LEFT)

        # Настройка веса колонок для растягивания
        for i in range(9):
            self.grid_columnconfigure(i, weight=1)

    def _toggle_filters(self):
        """Переключает состояние фильтров"""
        state = NORMAL if not self.accept_all_var.get() else DISABLED
        # Здесь можно добавить логику отключения полей если нужно

    def _configure_parser(self):
        """Открывает окно настройки конфигураций парсера"""
        # Собираем данные правила
        rule_data = self.get_rule_data()

        print(f"Открываем окно конфигураций для: {self.rd_raw.name}")

        # Открываем окно конфигураций
        config_window = ParserConfigWindow(self, rule_data)
        config_window.transient(self)
        config_window.grab_set()
        self.wait_window(config_window)

    def _delete_rule(self):
        """Удаляет это правило"""
        if self.on_delete:
            self.on_delete(self)
        crud.delete_email_filter(self.rd_raw.id)
        self.destroy()

    def get_rule_data(self):
        """Возвращает данные правила"""
        return crud.get_email_filter(self.rd_raw.id)


class FilterSettingsFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill=BOTH, expand=YES, padx=10, pady=10)
        self.filter_rules = []
        self._create_widgets()
        self._load_default_rules()

    def _create_widgets(self):
        # Заголовок и кнопка добавления
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=X, pady=(0, 15))

        ttk.Label(
            header_frame,
            text="Фильтрация входящих писем",
            font=("Helvetica", 14, "bold")
        ).pack(side=LEFT, anchor=W)

        ttk.Button(
            header_frame,
            text="+ Добавить правило",
            bootstyle=SUCCESS,
            command=self._add_new_rule
        ).pack(side=RIGHT)

        # Создаем заголовки таблицы
        self._create_table_headers()

        # Прокручиваемая область для правил
        self.scrolled_frame = ScrolledFrame(self, height=400)
        self.scrolled_frame.pack(fill=BOTH, expand=YES)

        self.rules_container = ttk.Frame(self.scrolled_frame)
        self.rules_container.pack(fill=X, padx=5)

        # Настройка веса колонок для растягивания
        for i in range(9):
            self.rules_container.grid_columnconfigure(i, weight=1)

    def _create_table_headers(self):
        """Создает заголовки таблицы"""
        headers = [
            ("Имя", 15),
            ("Email отправителя", 20),
            ("Тема содержит", 15),
            ("Тема НЕ содержит", 15),
            ("Расширения", 12),
            ("Имя файла содержит", 15),
            ("Имя файла НЕ содержит", 15),
            # ("Принимать все", 10),
            ("Действия", 16)
        ]

        header_frame = ttk.Frame(self)
        header_frame.pack(fill=X, pady=(0, 10))

        for i, (text, width) in enumerate(headers):
            ttk.Label(
                header_frame,
                text=text,
                font=("Helvetica", 9, "bold"),
                borderwidth=1,
                relief="solid",
                padding=5
            ).grid(row=0, column=i, padx=1, pady=1, sticky=EW)
            header_frame.grid_columnconfigure(i, weight=1)

    def _load_default_rules(self):
        """Загружает примеры боевых правил"""

        default_rules: list[Filters] = crud.list_email_filters()

        for rule_data in default_rules:
            self._add_rule_row(rule_data)

    def _add_new_rule(self):
        """Добавляет новое пустое правило"""
        self._add_rule_row()

    def _add_rule_row(self, rule_data=None):
        """Добавляет строку с правилом"""
        row_index = len(self.filter_rules)
        rule_row = FilterRuleRow(
            self.rules_container,
            rule_data,
            on_delete=self._delete_rule_row
        )
        rule_row.grid(row=row_index, column=0, columnspan=9, sticky=EW, pady=1)
        self.filter_rules.append(rule_row)

    def _delete_rule_row(self, rule_row):
        """Удаляет строку правила"""
        if rule_row in self.filter_rules:
            self.filter_rules.remove(rule_row)
        rule_row.destroy()
        # Переупаковываем оставшиеся строки
        self._rearrange_rows()

    def _rearrange_rows(self):
        """Переупаковывает строки после удаления"""
        for i, rule_row in enumerate(self.filter_rules):
            rule_row.grid(row=i, column=0, columnspan=9, sticky=EW, pady=1)

    def save_filters(self):
        """Сохраняет все фильтры"""
        filters_data = []
        for rule_row in self.filter_rules:
            if rule_row.winfo_exists():
                filters_data.append(rule_row.get_rule_data())

        # Здесь будет сохранение в БД
        ToastNotification(
            title="Сохранено",
            message=f"Сохранено {len(filters_data)} правил фильтрации",
            bootstyle=SUCCESS
        ).show_toast()
        return filters_data


def launch_price_parser():
    """Запускает парсер в дочернем окне с сохранением стилей"""
    from parser import PriceParserApp
    ToastNotification(
        title="Запуск парсера",
        message="Парсер цен запускается...",
        duration=2000
    ).show_toast()
    ps = PriceParserApp(parent=ttk.Toplevel(title="Парсер цен"))


def create_settings_frame(self, notebook):
    tab_settings = ttk.Frame(notebook)
    notebook.add(tab_settings, text="⚙️ Настройки")

    # Создаем Notebook для разделов настроек
    settings_notebook = ttk.Notebook(tab_settings)
    settings_notebook.pack(fill=BOTH, expand=YES, padx=10, pady=10)

    # Вкладка настроек почты
    email_tab = ttk.Frame(settings_notebook)
    settings_notebook.add(email_tab, text="📧 Настройки почты")
    EmailSettingsFrame(email_tab)

    # Вкладка фильтрации
    filter_tab = ttk.Frame(settings_notebook)
    settings_notebook.add(filter_tab, text="🔍 Фильтрация писем")
    filter_frame = FilterSettingsFrame(filter_tab)

    # Кнопка сохранения всех настроек
    bottom_frame = ttk.Frame(tab_settings)
    bottom_frame.pack(fill=X, padx=10, pady=10)

    ttk.Button(
        bottom_frame,
        text="Сохранить все настройки",
        bootstyle=SUCCESS,
        command=filter_frame.save_filters
    ).pack(side=RIGHT, padx=(10, 0))

    ttk.Button(
        bottom_frame,
        text="Запустить парсер",
        bootstyle=PRIMARY,
        command=launch_price_parser
    ).pack(side=RIGHT)
