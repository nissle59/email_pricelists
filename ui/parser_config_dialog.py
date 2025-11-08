import traceback
from typing import Self, TYPE_CHECKING
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.toast import ToastNotification
from ttkbootstrap.scrolled import ScrolledFrame
import json

from crud import list_vendors, list_configs_for_vendor, get_vendor_by_name, get_vendor_name_by_id, get_config_by_name, \
    update_config, get_email_filter_by_name, set_email_filter_vendor_id, update_email_filter, save_config, \
    delete_config, list_letters, find_attachment_by_filename
from models import Filters, ParsingConfig
from ya_client import client as email_client

class ParserConfigWindow(ttk.Toplevel):
    def __init__(self, parent, rule_data: Filters):
        super().__init__(parent)
        self.current_file = None
        self.vendors = list_vendors()
        self.configlist = []
        self.sender_email = rule_data.senders.split(";")
        self.rule_name = rule_data.name
        self.rule_data = rule_data
        self.configurations = []
        self.current_pattern = ""

        self.title(f"Конфигурации парсера - {self.rule_name}")
        self.geometry("1200x800")

        # Центрируем окно
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

        self._create_widgets()

    def _create_widgets(self):
        widgets = [
            {
                "text": "Email отправителя",
                "variable": "senders",
            },
            {
                "text": "Тема содержит",
                "variable": "subject_contains",
            },
            {
                "text": "Тема НЕ содержит",
                "variable": "subject_excludes",
            },
            {
                "text": "Расширения",
                "variable": "extensions",
            },
            {
                "text": "Имя файла содержит",
                "variable": "filename_contains",
            },
            {
                "text": "Имя файла НЕ содержит",
                "variable": "filename_excludes",
            }
        ]
        # Основной контейнер с разделением на две части
        main_container = ttk.Frame(self)
        main_container.pack(fill=BOTH, expand=YES, padx=10, pady=10)

        # Левая часть - конфигурации
        left_frame = ttk.Frame(main_container)
        left_frame.pack(side=LEFT, fill=BOTH, expand=YES, padx=(0, 10))

        # Правая часть - письма
        right_frame = ttk.LabelFrame(main_container, text="Результаты фильтрации писем")
        right_frame.pack(side=RIGHT, fill=BOTH, expand=YES, padx=(10, 0))
        right_frame.configure(width=400)

        # === ЛЕВАЯ ЧАСТЬ - КОНФИГУРАЦИИ ===

        # Заголовок
        ttk.Label(
            left_frame,
            text=f"Конфигурации парсера для: {self.rule_name}",
            font=("Helvetica", 12, "bold")
        ).pack(anchor=W, pady=(0, 10))

        # Информация о правиле
        info_frame = ttk.LabelFrame(left_frame, text="Текущее правило фильтрации")
        info_frame.pack(fill=X, pady=(0, 10))

        current_row = 0

        for widget in widgets:
            ttk.Label(info_frame, text=f"{widget['text']}:", width=15).grid(row=current_row, column=0, sticky=W, pady=2)
            var_name = widget.get("variable")
            # Создаем атрибут динамически
            setattr(self, f'{var_name}_var', ttk.StringVar(value=getattr(self.rule_data, var_name)))
            # Создаем Entry используя getattr
            entry = ttk.Entry(info_frame, textvariable=getattr(self, f'{var_name}_var'), width=25)
            entry.grid(row=current_row, column=1, sticky=W, pady=2, padx=5)
            current_row += 1

        def on_focus_out(event):
            print("Focus out event")
            new_vendor = self.rule_data.vendor.name
            print(new_vendor)
            self.configlist = list_configs_for_vendor(new_vendor)
            print(self.configlist)
            lframes = [item[1] for item in self.configs_frame.children.items()]
            try:
                vendor_id = get_vendor_by_name(new_vendor).id
                set_email_filter_vendor_id(self.rule_data.id, vendor_id)
            except Exception as e:
                print(e)

            for lframe in lframes:
                for item in [item[1] for item in lframe.children.items()]:
                    for i in [item[1] for item in item.children.items()]:
                        if isinstance(i, ttk.Combobox):
                            print("Found!")
                            try:
                                i['values'] = [c.name for c in self.configlist]
                            except:
                                i['values'] = []

        # ttk.Label(info_frame, text="Поставщик:", width=15).grid(row=current_row, column=0, sticky=W, pady=2)
        # vendor_name = get_vendor_name_by_id(self.rule_data.vendor_id)
        # self.rule_data.vendor.name = ttk.StringVar(value=vendor_name)
        # vendor_entry = ttk.Combobox(info_frame, textvariable=self.rule_data.vendor.name, values=[v.name for v in self.vendors],
        #                             width=25)
        # vendor_entry.grid(row=current_row, column=1, sticky=W, pady=2, padx=5)
        # vendor_entry.bind('<FocusOut>', on_focus_out)
        # vendor_entry.bind('<<ComboboxSelected>>', on_focus_out)
        # current_row += 1

        # Заголовок раздела конфигураций
        config_header = ttk.Frame(left_frame)
        config_header.pack(fill=X, pady=(0, 10))

        ttk.Label(
            config_header,
            text="Конфигурации парсера:",
            font=("Helvetica", 10, "bold")
        ).pack(side=LEFT, anchor=W)

        ttk.Button(
            config_header,
            text="+ Добавить конфигурацию",
            bootstyle=SUCCESS,
            command=self._add_configuration
        ).pack(side=RIGHT)

        # Прокручиваемая область для конфигураций
        self.configs_frame = ScrolledFrame(left_frame, height=300)
        self.configs_frame.pack(fill=BOTH, expand=YES, pady=(0, 15))

        # Кнопки внизу слева
        left_buttons = ttk.Frame(left_frame)
        left_buttons.pack(fill=X, pady=10)

        ttk.Button(
            left_buttons,
            text="Сохранить все конфигурации",
            bootstyle=SUCCESS,
            command=self._save_all_configurations
        ).pack(side=RIGHT, padx=(10, 0))

        ttk.Button(
            left_buttons,
            text="Загрузить письма",
            bootstyle=INFO,
            command=self._load_emails
        ).pack(side=RIGHT, padx=(10, 0))

        # === ПРАВАЯ ЧАСТЬ - ПИСЬМА ===

        # Статус
        self.email_status_var = ttk.StringVar(value="Нажмите 'Загрузить письма' для получения данных")
        ttk.Label(
            right_frame,
            textvariable=self.email_status_var,
            font=("Helvetica", 9)
        ).pack(anchor=W, padx=10, pady=(10, 5))

        # Таблица с письмами
        email_tree_frame = ttk.Frame(right_frame)
        email_tree_frame.pack(fill=BOTH, expand=YES, padx=10, pady=5)

        self.email_tree = ttk.Treeview(
            email_tree_frame,
            columns=("subject", "filename", "date", "config"),
            show="headings",
            height=20
        )

        self.email_tree.heading("subject", text="Тема")
        self.email_tree.heading("filename", text="Файл")
        self.email_tree.heading("date", text="Дата")
        self.email_tree.heading("config", text="Конфигурация")

        self.email_tree.column("subject", width=150)
        self.email_tree.column("filename", width=120)
        self.email_tree.column("date", width=80)
        self.email_tree.column("config", width=100)

        # Скроллбары для таблицы писем
        email_vsb = ttk.Scrollbar(email_tree_frame, orient=VERTICAL, command=self.email_tree.yview)
        email_hsb = ttk.Scrollbar(email_tree_frame, orient=HORIZONTAL, command=self.email_tree.xview)
        self.email_tree.configure(yscrollcommand=email_vsb.set, xscrollcommand=email_hsb.set)

        self.email_tree.grid(row=0, column=0, sticky="nsew")
        email_vsb.grid(row=0, column=1, sticky="ns")
        email_hsb.grid(row=1, column=0, sticky="ew")

        email_tree_frame.grid_rowconfigure(0, weight=1)
        email_tree_frame.grid_columnconfigure(0, weight=1)

        def on_email_tree_select(event):
            selected_item = self.email_tree.selection()[0]

            self.current_file = find_attachment_by_filename(self.email_tree.item(selected_item, "values")[1]).file_path
            print(f"Selected configuration: {self.current_file}")

        self.email_tree.bind("<<TreeviewSelect>>", on_email_tree_select)

        # Подсказка
        ttk.Label(
            right_frame,
            text="💡 Цвет строк показывает соответствие шаблонам конфигураций",
            font=("Helvetica", 8),
            style="secondary.TLabel"
        ).pack(anchor=W, padx=10, pady=(5, 10))

        # Загружаем моковые данные
        self._load_configurations()
        self._load_emails()
        # self._load_mock_configurations()

    def _load_configurations(self):
        """Загружает примеры конфигураций для демонстрации"""
        mock_configs = [
            {
                'name': 'Основной прайс',
                'filename_pattern': 'прайс',
                'vendor': 'Техносите',
                'config_name': 'Техносите_основной'
            },
            {
                'name': 'Акционный прайс',
                'filename_pattern': 'акция',
                'vendor': 'Техносите',
                'config_name': 'Техносите_акции'
            },
            {
                'name': 'Остатки',
                'filename_pattern': 'остатки',
                'vendor': 'Техносите',
                'config_name': 'Техносите_остатки'
            }
        ]

        configs = list_configs_for_vendor(self.rule_data.vendor.name)
        print(self.rule_data.vendor.name)
        for config_data in configs:
            print(config_data)
            self._add_config_frame(config_data)

    def _load_mock_configurations(self):
        """Загружает примеры конфигураций для демонстрации"""
        mock_configs = [
            {
                'name': 'Основной прайс',
                'filename_pattern': 'прайс',
                'vendor': 'Техносите',
                'config_name': 'Техносите_основной'
            },
            {
                'name': 'Акционный прайс',
                'filename_pattern': 'акция',
                'vendor': 'Техносите',
                'config_name': 'Техносите_акции'
            },
            {
                'name': 'Остатки',
                'filename_pattern': 'остатки',
                'vendor': 'Техносите',
                'config_name': 'Техносите_остатки'
            }
        ]

        for config_data in mock_configs:
            self._add_config_frame(config_data)


    def _load_emails(self):
        """Моковая функция загрузки писем"""
        # Создаем моковые данные писем
        mock_emails = [
            {"subject": "Прайс-лист на ноябрь", "filename": "прайс_ноябрь.xlsx", "date": "2024-11-20"},
            {"subject": "Акционные товары", "filename": "акция_декабрь.xls", "date": "2024-11-18"},
            {"subject": "Остатки на складе", "filename": "остатки_склад.xlsx", "date": "2024-11-15"},
            {"subject": "Внешний заказ", "filename": "внешний_заказ.xlsx", "date": "2024-11-10"},
            {"subject": "Прайс обновленный", "filename": "прайс_новый.xlsm", "date": "2024-11-08"},
            {"subject": "Прайс-лист", "filename": "price_list.xlsx", "date": "2024-11-05"},
            {"subject": "Акция недели", "filename": "weekly_sale.xls", "date": "2024-11-03"},
            {"subject": "Остатки товаров", "filename": "stock_balance.xlsx", "date": "2024-11-01"},
        ]
        emails = []
        if self.rule_data.senders:
            if self.rule_data.vendor_id:
                emails_instances = list_letters(self.rule_data.vendor_id)
                emails = [
                    {
                        "subject": email.subject,
                        "filename": a.file_name,
                        "date": email.date.strftime("%Y-%m-%d %H:%M")
                    }
                    for email in emails_instances
                    for a in email.attachments
                ]

            # Фильтруем по правилу
            filtered_emails = self._filter_emails_by_rule(emails)

            # Обновляем статус
            self.email_status_var.set(f"Найдено писем: {len(filtered_emails)}")

            # Показываем письма в таблице
            self._display_emails_in_tree(filtered_emails)

    def _load_emails_mock(self):
        """Моковая функция загрузки писем"""
        # Создаем моковые данные писем
        mock_emails = [
            {"subject": "Прайс-лист на ноябрь", "filename": "прайс_ноябрь.xlsx", "date": "2024-11-20"},
            {"subject": "Акционные товары", "filename": "акция_декабрь.xls", "date": "2024-11-18"},
            {"subject": "Остатки на складе", "filename": "остатки_склад.xlsx", "date": "2024-11-15"},
            {"subject": "Внешний заказ", "filename": "внешний_заказ.xlsx", "date": "2024-11-10"},
            {"subject": "Прайс обновленный", "filename": "прайс_новый.xlsm", "date": "2024-11-08"},
            {"subject": "Прайс-лист", "filename": "price_list.xlsx", "date": "2024-11-05"},
            {"subject": "Акция недели", "filename": "weekly_sale.xls", "date": "2024-11-03"},
            {"subject": "Остатки товаров", "filename": "stock_balance.xlsx", "date": "2024-11-01"},
        ]

        # Фильтруем по правилу
        filtered_emails = self._filter_emails_by_rule(mock_emails)

        # Обновляем статус
        self.email_status_var.set(f"Найдено писем: {len(filtered_emails)}")

        # Показываем письма в таблице
        self._display_emails_in_tree(filtered_emails)

    def _filter_emails_by_rule(self, emails):
        """Фильтрует письма по текущему правилу"""
        filtered = []

        for email in emails:
            # Проверка расширения
            if self.rule_data.extensions:
                ext_ok = any(email['filename'].lower().endswith(ext.strip().lower())
                             for ext in self.rule_data.extensions.split(','))
                if not ext_ok:
                    continue

            # Проверка темы
            if self.rule_data.subject_contains:
                subject_ok = any(keyword.strip().lower() in email['subject'].lower()
                                 for keyword in self.rule_data.subject_contains.split(';'))
                if not subject_ok:
                    continue

            if self.rule_data.subject_excludes:
                subject_ex_ok = not any(keyword.strip().lower() in email['subject'].lower()
                                         for keyword in self.rule_data.subject_excludes.split(';'))
                if not subject_ex_ok:
                    continue

            # Проверка имени файла (содержит)
            if self.rule_data.filename_contains:
                filename_ok = any(keyword.strip().lower() in email['filename'].lower()
                                  for keyword in self.rule_data.filename_contains.split(';'))
                if not filename_ok:
                    continue

            # Проверка имени файла (НЕ содержит)
            if self.rule_data.filename_excludes:
                filename_ex_ok = not any(keyword.strip().lower() in email['filename'].lower()
                                         for keyword in self.rule_data.filename_excludes.split(';'))
                if not filename_ex_ok:
                    continue

            filtered.append(email)

        return filtered

    def _display_emails_in_tree(self, emails):
        """Отображает письма в таблице справа"""
        # Очищаем таблицу
        for item in self.email_tree.get_children():
            self.email_tree.delete(item)

        # Цвета для разных конфигураций
        # config_colors = {
        #     'Основной прайс': '#e6f3ff',  # голубой
        #     'Акционный прайс': '#fff0e6',  # оранжевый
        #     'Остатки': '#e6ffe6',  # зеленый
        # }

        for email in emails:
            # Определяем, какая конфигурация подходит для этого файла
            matched_config = self._find_matching_config(email['filename'])

            # Вставляем запись
            item_id = self.email_tree.insert(
                "",
                END,
                values=(
                    email['subject'],
                    email['filename'],
                    email['date'],
                    matched_config if matched_config else "Не назначено"
                )
            )

            # Раскрашиваем строку если есть совпадение
            # if matched_config and matched_config in config_colors:
            #     self.email_tree.item(item_id, tags=(matched_config,))

        # Настраиваем теги для цветов
        # for config_name, color in config_colors.items():
        #     self.email_tree.tag_configure(config_name, background=color)

    def _find_matching_config(self, filename):
        """Находит конфигурацию, подходящую для файла"""
        filename_lower = filename.lower()

        for config_frame in self.configurations:
            if not config_frame.winfo_exists():
                continue

            pattern = config_frame.vars['pattern'].get().strip().lower()
            if pattern and pattern in filename_lower:
                return config_frame.vars['config_name'].get()

        return None

    def _on_pattern_change(self, pattern_var, *args):
        """Обработчик изменения шаблона файла"""
        new_pattern = pattern_var.get()
        if new_pattern != self.current_pattern:
            self.current_pattern = new_pattern
            # Обновляем отображение писем
            if hasattr(self, 'email_tree') and self.email_tree.get_children():
                self._update_email_display()

    def _update_email_display(self):
        """Обновляет отображение писем при изменении шаблонов"""
        # Получаем текущие данные из таблицы
        emails = []
        for item in self.email_tree.get_children():
            values = self.email_tree.item(item)['values']
            emails.append({
                'subject': values[0],
                'filename': values[1],
                'date': values[2]
            })

        # Перерисовываем таблицу
        self._display_emails_in_tree(emails)

    def _add_configuration(self):
        """Добавляет новую конфигурацию парсера"""
        # config_data = {
        #     'name': 'Новая конфигурация',
        #     'filename_pattern': '',
        #     'vendor': self.rule_data.vendor.name,
        #     'config_name': f"{self.rule_data.vendor.name}_новая"
        # }
        config_data = ParsingConfig(
            name='Новая конфигурация',
            vendor_id=self.rule_data.vendor_id
        )
        self._add_config_frame(config_data)

    def _add_config_frame(self, config_data):
        """Добавляет фрейм конфигурации"""
        config_frame = ttk.LabelFrame(self.configs_frame, text=config_data.name)
        config_frame.pack(fill=X, pady=5, padx=5)

        # Основные настройки конфигурации
        settings_frame = ttk.Frame(config_frame)
        settings_frame.pack(fill=X, padx=10, pady=10)

        # Название конфигурации
        ttk.Label(settings_frame, text="Название:", width=12).grid(row=0, column=0, sticky=W, pady=2)
        config_var = ttk.StringVar(value=config_data.name)
        config_entry = ttk.Combobox(settings_frame, textvariable=config_var, values=[c.name for c in self.configlist],
                                    width=20)
        config_entry.grid(row=0, column=1, sticky=W, pady=2, padx=5)

        # Шаблон имени файла
        ttk.Label(settings_frame, text="Шаблон файла:", width=12).grid(row=1, column=0, sticky=W, pady=2)
        pattern_var = ttk.StringVar(value=config_data.filename_template)
        pattern_entry = ttk.Entry(settings_frame, textvariable=pattern_var, width=20)
        pattern_entry.grid(row=1, column=1, sticky=W, pady=2, padx=5)

        #ttk.Label(settings_frame, text="В общий прайс:", width=12).grid(row=2, column=0, sticky=W, pady=2)
        active_var = ttk.BooleanVar(value=config_data.active)
        active_check = ttk.Checkbutton(settings_frame, text="ВКЛ правило", variable=active_var)
        active_check.grid(row=2, column=0, sticky=W, pady=2, padx=5)

        common_var = ttk.BooleanVar(value=config_data.to_common)
        common_check = ttk.Checkbutton(settings_frame, text="в общий прайс", variable=common_var)
        common_check.grid(row=3, column=0, sticky=W, pady=2, padx=5)

        original_var = ttk.BooleanVar(value=config_data.save_original)
        original_check = ttk.Checkbutton(settings_frame, text="сохранить оригинал", variable=original_var)
        original_check.grid(row=2, column=1, sticky=W, pady=2, padx=5)

        parsed_var = ttk.BooleanVar(value=config_data.save_parsed)
        parsed_check = ttk.Checkbutton(settings_frame, text="сохранить обработанный", variable=parsed_var)
        parsed_check.grid(row=3, column=1, sticky=W, pady=2, padx=5)

        # Привязываем обработчик изменения шаблона
        pattern_var.trace('w', lambda *args: self._on_pattern_change(pattern_var))

        # Кнопки действий
        btn_frame = ttk.Frame(settings_frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=5, sticky=W)

        ttk.Button(
            btn_frame,
            text="Настроить парсер",
            bootstyle=PRIMARY,
            command=lambda: self._configure_parser({
                'vendor': self.rule_data.vendor.name,
                'config_name': config_var.get()
            })
        ).pack(side=LEFT, padx=(0, 10))

        ttk.Button(
            btn_frame,
            text="Удалить",
            bootstyle=DANGER,
            command=lambda: self._delete_config(config_frame)
        ).pack(side=LEFT)

        # Сохраняем ссылки на переменные
        config_frame.vars = {
            'pattern': pattern_var,
            'vendor': self.rule_data.vendor.name,
            'config_name': config_var,
            'active': active_var,
            'save_original': original_var,
            'save_parsed': parsed_var,
            'to_common': common_var
        }

        self.configurations.append(config_frame)

    def _delete_config(self, config_frame):
        """Удаляет конфигурацию"""
        if config_frame in self.configurations:
            self.configurations.remove(config_frame)
        config_frame.destroy()
        cfg_id = get_config_by_name(config_frame.vars['config_name'].get()).id
        delete_config(cfg_id)
        # Обновляем отображение писем
        self._update_email_display()

    def _configure_parser(self, config_data):
        """Открывает настройки парсера для этой конфигурации"""
        try:
            from parser import PriceParserApp
            if not self.current_file:
                ToastNotification(
                    title="Ошибка",
                    message=f"Выберите пример файла для парсинга",
                    bootstyle=DANGER
                ).show_toast()
                return
            print(config_data['vendor'])
            parser_window = PriceParserApp(
                parent=self,
                vendor=config_data['vendor'],
                file_in=self.current_file,
                file_prefix="",
                config_name=config_data['config_name']
            )
            parser_window.transient(self)
            parser_window.grab_set()
            self.wait_window(parser_window)
        except Exception as e:
            print(e)
            traceback.print_exc()
            ToastNotification(
                title="Ошибка",
                message=f"Ошибка открытия парсера: {e}",
                bootstyle=DANGER
            ).show_toast()

    def _save_all_configurations(self):
        """Сохраняет все конфигурации"""
        saved_configs = []

        update_email_filter(
            self.rule_data.id,
            Filters(
                name=self.rule_name,
                senders=self.senders_var.get(),
                subject_contains=self.subject_contains_var.get(),
                subject_excludes=self.subject_excludes_var.get(),
                filename_contains=self.filename_contains_var.get(),
                filename_excludes=self.filename_excludes_var.get(),
                extensions=self.extensions_var.get()
            )
        )

        for config_frame in self.configurations:
            if config_frame.winfo_exists():
                config_data = {
                    'filename_pattern': config_frame.vars['pattern'].get(),
                    #'vendor': config_frame.vars['vendor'].get(),
                    'config_name': config_frame.vars['config_name'].get()
                }
                try:
                    print([config_frame.vars[v].get() for v in config_frame.vars])
                    conf = save_config(
                        config_name=config_frame.vars['config_name'].get(),
                        vendor_name=self.rule_data.vendor.name,
                        filename_pattern=config_frame.vars['pattern'].get(),
                        active=config_frame.vars['active'].get(),
                        to_common=config_frame.vars['to_common'].get(),
                        save_original=config_frame.vars['save_original'].get(),
                        save_parsed=config_frame.vars['save_parsed'].get(),
                    )
                    print('Saved')
                except Exception as e:
                    print(e)
                saved_configs.append(config_data)

        ToastNotification(
            title="Сохранено",
            message=f"Сохранено {len(saved_configs)} конфигураций парсера",
            bootstyle=SUCCESS
        ).show_toast()
