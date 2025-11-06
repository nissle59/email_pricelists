# ui/main_frame.py
from datetime import datetime

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.tableview import Tableview
from ttkbootstrap.toast import ToastNotification
from ttkbootstrap.validation import add_regex_validation

from crud import list_letters, list_vendors, set_vendor_last_load, list_configs_for_vendor
from utils.parser_logic import parse
from ya_client import client as email_client


class MainFrame:
    def __init__(self, notebook):
        self.selected_vendor_var = ttk.StringVar()
        self.days_entry_var = None
        self.tab_main = ttk.Frame(notebook)
        notebook.add(self.tab_main, text="🏠 Главная")
        self.setup_ui()

    def setup_ui(self):
        # Заголовок
        ttk.Label(
            self.tab_main,
            text="Парсер прайс-листов",
            font=("Helvetica", 18, "bold")
        ).pack(pady=20)

        # Основной контейнер
        main_container = ttk.Frame(self.tab_main)
        main_container.pack(fill=BOTH, expand=YES, padx=20, pady=10)

        # Создаем notebook для этапов
        self.steps_notebook = ttk.Notebook(main_container)
        self.steps_notebook.pack(fill=BOTH, expand=YES)

        # Этап 1 - Загрузка
        self.setup_loading_tab()

        # Этап 2 - Конфигурация парсинга
        self.setup_parsing_config_tab()

    def setup_loading_tab(self):
        """Настройка вкладки загрузки прайс-листов"""
        tab_loading = ttk.Frame(self.steps_notebook)
        self.steps_notebook.add(tab_loading, text="1️⃣ Загрузка прайс-листов")

        # Период загрузки
        period_frame = ttk.LabelFrame(tab_loading, text="Период загрузки", padding=15)
        period_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(period_frame, text="Загрузить данные за последние:").grid(
            row=0, column=0, sticky=W, padx=(0, 10)
        )
        self.days_entry_var = ttk.StringVar(value="7")
        self.days_entry = ttk.Entry(period_frame, width=10, textvariable=self.days_entry_var)

        #self.days_entry.insert(0, "7")  # По умолчанию 7 дней
        self.days_entry.grid(row=0, column=1, padx=(0, 10))

        ttk.Label(period_frame, text="дней").grid(row=0, column=2, sticky=W)

        # Валидация - только цифры
        add_regex_validation(self.days_entry, r'^\d+$')

        # Выбор поставщиков
        suppliers_frame = ttk.LabelFrame(tab_loading, text="Выбор поставщиков", padding=15)
        suppliers_frame.pack(fill=BOTH, expand=YES, pady=(0, 10))

        # Фрейм с кнопками управления выбором
        suppliers_controls = ttk.Frame(suppliers_frame)
        suppliers_controls.pack(fill=X, pady=(0, 10))

        # ttk.Button(
        #     suppliers_controls,
        #     text="Выбрать всех",
        #     bootstyle="success-outline",
        #     command=self.select_all_suppliers
        # ).pack(side=LEFT, padx=(0, 5))
        #
        # ttk.Button(
        #     suppliers_controls,
        #     text="Снять выделение",
        #     bootstyle="warning-outline",
        #     command=self.deselect_all_suppliers
        # ).pack(side=LEFT, padx=(0, 5))

        # Таблица поставщиков
        columns = [
            {"text": "ID", "stretch": False},
            {"text": "Поставщик", "stretch": True},
            {"text": "Активен", "stretch": False},
            {"text": "Последняя загрузка", "stretch": True}
        ]

        self.vendors_list = [[str(vendor.id), vendor.name, "Да" if vendor.active else "Нет", vendor.last_load.strftime('%Y-%m-%d %H:%M:%S') if vendor.last_load else ''] for vendor in list_vendors()]

        self.suppliers_table = Tableview(
            suppliers_frame,
            coldata=columns,
            rowdata=self.vendors_list,
            paginated=True,
            searchable=True,
            bootstyle=PRIMARY,
            #stripecolor=("gray", None),
        )
        self.suppliers_table.pack(fill=BOTH, expand=YES)

        # Кнопка запуска загрузки
        ttk.Button(
            tab_loading,
            text="🚀 Начать загрузку",
            bootstyle="success",
            command=self.start_loading,
            width=20
        ).pack(pady=20)

        # Прогресс бар загрузки
        self.loading_progress = ttk.Progressbar(
            tab_loading,
            bootstyle="success-striped",
            mode='determinate'
        )
        self.loading_progress.pack(fill=X, pady=(0, 10))

        # Статус загрузки
        self.loading_status = ttk.Label(
            tab_loading,
            text="Готов к загрузке",
            font=("Helvetica", 10)
        )
        self.loading_status.pack(pady=(0, 10))

    def setup_parsing_config_tab(self):
        """Настройка вкладки конфигурации парсинга"""
        tab_parsing = ttk.Frame(self.steps_notebook)
        self.steps_notebook.add(tab_parsing, text="2️⃣ Конфигурация парсинга")

        # Фильтры по поставщикам
        filters_frame = ttk.LabelFrame(tab_parsing, text="Фильтры по поставщикам", padding=15)
        filters_frame.pack(fill=X, pady=(0, 10))

        # Выбор поставщика для настройки фильтров
        supplier_select_frame = ttk.Frame(filters_frame)
        supplier_select_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(supplier_select_frame, text="Поставщик:").pack(side=LEFT, padx=(0, 10))

        self.supplier_combobox = ttk.Combobox(
            supplier_select_frame,
            values=[v[1] for v in self.vendors_list],  # Будет заполнено из БД
            state="readonly",
            width=30,
            textvariable=self.selected_vendor_var
        )
        self.supplier_combobox.pack(side=LEFT, padx=(0, 10))
        self.supplier_combobox.bind('<<ComboboxSelected>>', self.on_supplier_selected)

        # Таблица конфигураций парсинга
        config_frame = ttk.LabelFrame(tab_parsing, text="Конфигурации парсинга", padding=15)
        config_frame.pack(fill=BOTH, expand=YES, pady=(0, 10))

        columns = [
            {"text": "ID", "stretch": False, "width": 50},
            {"text": "Название конфигурации", "stretch": True},
            {"text": "Используется", "stretch": False, "width": 100},
            {"text": "В общий прайс", "stretch": False, "width": 100},
            {"text": "Сохранить оригинал", "stretch": False, "width": 150},
            {"text": "Сохранить обработанный", "stretch": False, "width": 150}
        ]

        self.config_table = Tableview(
            config_frame,
            coldata=columns,
            rowdata=[],
            paginated=True,
            searchable=True,
            bootstyle=PRIMARY,
            #stripecolor=("gray", None),
        )
        self.config_table.pack(fill=BOTH, expand=YES)

        # Кнопки управления конфигурациями
        buttons_frame = ttk.Frame(config_frame)
        buttons_frame.pack(fill=X, pady=(10, 0))

        # ttk.Button(
        #     buttons_frame,
        #     text="✏️ Редактировать конфигурацию",
        #     bootstyle="primary",
        #     command=self.edit_config
        # ).pack(side=LEFT, padx=(0, 5))
        #
        # ttk.Button(
        #     buttons_frame,
        #     text="🔄 Применить изменения",
        #     bootstyle="success",
        #     command=self.apply_config_changes
        # ).pack(side=LEFT, padx=(0, 5))
        #
        # ttk.Button(
        #     buttons_frame,
        #     text="➕ Новая конфигурация",
        #     bootstyle="info",
        #     command=self.create_new_config
        # ).pack(side=LEFT, padx=(0, 5))

        # Кнопка запуска парсинга
        ttk.Button(
            tab_parsing,
            text="⚙️ Запустить парсинг",
            bootstyle="danger",
            command=self.start_parsing,
            width=20
        ).pack(pady=20)

        # Прогресс бар парсинга
        self.parsing_progress = ttk.Progressbar(
            tab_parsing,
            bootstyle="danger-striped",
            mode='determinate'
        )
        self.parsing_progress.pack(fill=X, pady=(0, 10))

        # Статус парсинга
        self.parsing_status = ttk.Label(
            tab_parsing,
            text="Готов к парсингу",
            font=("Helvetica", 10)
        )
        self.parsing_status.pack(pady=(0, 10))

    def select_all_suppliers(self):
        """Выбрать всех поставщиков"""
        # Здесь будет логика выбора всех поставщиков в таблице
        pass

    def deselect_all_suppliers(self):
        """Снять выделение со всех поставщиков"""
        # Здесь будет логика снятия выделения со всех поставщиков
        pass

    def start_loading(self):
        """Запуск загрузки прайс-листов"""
        email_client.get_all_prices(days=int(self.days_entry_var.get()))
        for vid, _, _, _ in self.vendors_list:
            set_vendor_last_load(vid, datetime.now())
        self.vendors_list = [[str(vendor.id), vendor.name, "Да" if vendor.active else "Нет", vendor.last_load.strftime('%Y-%m-%d %H:%M:%S') if vendor.last_load else ''] for vendor in list_vendors()]
        self.suppliers_table.delete_rows()
        self.suppliers_table.insert_rows(0, self.vendors_list)

    def on_supplier_selected(self, event):
        """Обработчик выбора поставщика"""
        self.config_list = [
            [
                str(config.id),
                config.name,
                "Да" if config.active else "Нет",
                "Да" if config.to_common else "Нет",
                "Да" if config.save_original else "Нет",
                "Да" if config.save_parsed else "Нет",
            ]
            for config in list_configs_for_vendor(self.selected_vendor_var.get())
        ]
        self.config_table.delete_rows()
        self.config_table.insert_rows(0, self.config_list)

    def edit_config(self):
        """Редактирование выбранной конфигурации"""
        # Здесь будет открытие диалога редактирования конфигурации
        pass

    def apply_config_changes(self):
        """Применение изменений конфигураций"""
        # Здесь будет сохранение изменений в БД
        pass

    def create_new_config(self):
        """Создание новой конфигурации"""
        # Здесь будет открытие диалога создания новой конфигурации
        pass

    def start_parsing(self):
        """Запуск парсинга"""
        fname = 'price.xlsx'
        days_depth = 7
        parse(fname, days_depth)
        ToastNotification(
            title="Сохранено",
            message=f"Прайс-лист {fname} сохранён",
            bootstyle=SUCCESS
        ).show_toast()

    def load_suppliers_data(self):
        """Загрузка данных поставщиков из БД"""
        # TODO: Загрузка данных из БД через SQLAlchemy
        # Пример:
        # suppliers = self.db_session.query(Supplier).all()
        # Обновление таблицы suppliers_table
        pass

    def load_parsing_configs(self, supplier_id):
        """Загрузка конфигураций парсинга для поставщика"""
        # TODO: Загрузка конфигураций из БД через SQLAlchemy
        # Пример:
        # configs = self.db_session.query(ParsingConfig).filter_by(supplier_id=supplier_id).all()
        # Обновление таблицы config_table
        pass