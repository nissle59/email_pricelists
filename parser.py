import json
import re
import traceback

import pandas as pd
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.toast import ToastNotification
from functools import partial
from pathlib import Path
from tkinter import filedialog, simpledialog, messagebox

import crud
import utils.db
from utils.convert_df import to_excel_with_role_widths
from utils.file_reader import read_excel_safe
from utils.stock_normalizer import normalize_stock_value

utils.db.init_db()


class QuantumConfigDialog(ttk.Toplevel):
    """Диалог для настройки сложной логики кванта"""

    def __init__(self, parent, available_columns, quantum_config):
        super().__init__(parent)
        self.title("Настройка логики кванта")
        self.geometry("800x700")
        self.transient(parent)
        self.grab_set()
        self.config = quantum_config
        print(self.config)

        # Центрируем окно
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

        self.available_columns = available_columns
        self.result = None

        self._build_ui()

    def _build_ui(self):
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=BOTH, expand=YES, padx=10, pady=10)

        # Заголовок
        ttk.Label(main_frame, text="Настройка логики для колонки 'Квант'",
                  font="-size 12 -weight bold").pack(pady=(0, 15))

        # Описание проблемы
        desc_text = (
            "Если в колонке 'Квант' указаны единицы измерения (шт, кор, бл и т.д.) "
            "вместо чисел, настройте соответствие между единицами измерения "
            "и колонками с количеством штук."
        )
        desc_label = ttk.Label(main_frame, text=desc_text, wraplength=580, justify=LEFT)
        desc_label.pack(pady=(0, 15))

        # Фрейм для основной колонки кванта
        quantum_frame = ttk.LabelFrame(main_frame, text="Основная колонка кванта")
        quantum_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(quantum_frame, text="Колонка с единицами измерения:").pack(anchor=W, pady=(5, 0))
        try:
            q_col = self.config.get("quantum_column", "(не выбрано)")
        except:
            q_col = "(не выбрано)"
        self.quantum_var = ttk.StringVar(value=q_col)
        quantum_cmb = ttk.Combobox(quantum_frame, textvariable=self.quantum_var,
                                   values=["(не выбрано)"] + self.available_columns)
        quantum_cmb.pack(fill=X, padx=5, pady=5)

        # Фрейм для сопоставления единиц измерения
        mapping_frame = ttk.LabelFrame(main_frame, text="Сопоставление единиц измерения")
        mapping_frame.pack(fill=BOTH, expand=YES, pady=(0, 10))

        # Прокручиваемая область для сопоставлений
        canvas = ttk.Canvas(mapping_frame, height=200)
        scrollbar = ttk.Scrollbar(mapping_frame, orient=VERTICAL, command=canvas.yview)
        self.mappings_frame = ttk.Frame(canvas)

        self.mappings_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.mappings_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar.pack(side=RIGHT, fill=Y)

        # Предустановленные сопоставления
        self.mappings = []
        try:
            for key, value in self.config.get("unit_mappings").items():
                self._add_mapping_row(key, value)
        except:
            self._add_mapping_row("шт", "1")  # По умолчанию для штук
            self._add_mapping_row("шт.", "1")
            self._add_mapping_row("блок", "Штук в блоке")
            self._add_mapping_row("бл", "Штук в блоке")
            self._add_mapping_row("Дисплейбокс", "Штук в блоке")
            self._add_mapping_row("кор", "Штук в коробке")
            self._add_mapping_row("кор.", "Штук в коробке")


        # Кнопка добавления нового сопоставления
        ttk.Button(mapping_frame, text="+ Добавить сопоставление",
                   command=self._add_mapping_row, bootstyle=OUTLINE).pack(pady=5)

        # Фрейм для колонок с количествами
        quantity_frame = ttk.LabelFrame(main_frame, text="Колонки с количеством штук")
        quantity_frame.pack(fill=X, pady=(0, 10))

        # Штук в коробке
        ttk.Label(quantity_frame, text="Колонка 'Штук в коробке':").pack(anchor=W, pady=(5, 0))
        try:
            box_q = self.config.get("box_quantity_column", "(не выбрано)")
        except:
            box_q = "(не выбрано)"
        self.box_qty_var = ttk.StringVar(value=box_q)
        box_cmb = ttk.Combobox(quantity_frame, textvariable=self.box_qty_var,
                               values=["(не выбрано)"] + self.available_columns)
        box_cmb.pack(fill=X, padx=5, pady=(0, 5))

        # Штук в блоке
        ttk.Label(quantity_frame, text="Колонка 'Штук в блоке':").pack(anchor=W, pady=(5, 0))
        try:
            block_q = self.config.get("block_quantity_column", "(не выбрано)")
        except:
            block_q = "(не выбрано)"
        self.block_qty_var = ttk.StringVar(value=block_q)
        block_cmb = ttk.Combobox(quantity_frame, textvariable=self.block_qty_var,
                                 values=["(не выбрано)"] + self.available_columns)
        block_cmb.pack(fill=X, padx=5, pady=(0, 5))

        # Кнопки
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=X, pady=(10, 0))

        ttk.Button(button_frame, text="Отмена", bootstyle=SECONDARY,
                   command=self.destroy).pack(side=LEFT)

        ttk.Button(button_frame, text="Сохранить", bootstyle=SUCCESS,
                   command=self._save_config).pack(side=RIGHT)

    def _add_mapping_row(self, unit="", column=""):
        """Добавляет строку для сопоставления единицы измерения"""
        row_frame = ttk.Frame(self.mappings_frame)
        row_frame.pack(fill=X, pady=2)

        # Единица измерения
        unit_entry = ttk.Entry(row_frame, width=15)
        unit_entry.insert(0, unit)
        unit_entry.pack(side=LEFT, padx=(0, 5))

        # Стрелка
        ttk.Label(row_frame, text="→").pack(side=LEFT, padx=5)

        # Колонка с количеством
        column_cmb = ttk.Combobox(row_frame, width=20,
                                  values=["(не выбрано)"] + self.available_columns + ["1"])
        if column:
            column_cmb.set(column)
        else:
            column_cmb.set("(не выбрано)")
        column_cmb.pack(side=LEFT, padx=(0, 5))

        # Кнопка удаления
        btn = ttk.Button(row_frame, text="×", width=3, bootstyle=DANGER,
                         command=lambda: row_frame.destroy())
        btn.pack(side=LEFT)

        self.mappings.append((unit_entry, column_cmb))

    def _save_config(self):
        """Сохраняет конфигурацию"""
        config = {
            'quantum_column': self.quantum_var.get() if self.quantum_var.get() != "(не выбрано)" else None,
            'unit_mappings': {},
            'box_quantity_column': self.box_qty_var.get() if self.box_qty_var.get() != "(не выбрано)" else None,
            'block_quantity_column': self.block_qty_var.get() if self.block_qty_var.get() != "(не выбрано)" else None
        }

        # Собираем сопоставления единиц измерения
        for unit_entry, column_cmb in self.mappings:
            try:
                unit = unit_entry.get().strip()
                column = column_cmb.get()

                if unit and column != "(не выбрано)":
                    config['unit_mappings'][unit] = column
            except Exception as e:
                print(e)

        if not config['quantum_column']:
            messagebox.showerror("Ошибка", "Выберите колонку с единицами измерения")
            return

        if not config['unit_mappings']:
            messagebox.showerror("Ошибка", "Добавьте хотя бы одно сопоставление единиц измерения")
            return

        self.result = config
        self.destroy()



class PriceParserApp(ttk.Toplevel):
    def __init__(self, parent=None, vendor=None, file_in=None, file_prefix: str = "", config_name: str | None = None):
        if parent is None:
            self.parent = ttk.Window(title="Парсер цен")
        else:
            self.parent = parent

        print(file_in)
        super().__init__(self.parent)
        self.geometry("1200x800")
        # Добавляем атрибут для хранения конфигурации кванта
        self.quantum_config = None
        self.resizable(True, True)
        # Центрируем окно парсера
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

        # Если не переданы vendor и file_in, показываем окно выбора
        if vendor is None or file_in is None:
            self._show_file_vendor_selection()
        else:
            self._initialize_app(vendor, file_in, file_prefix, config_name)

    def _show_file_vendor_selection(self):
        """Показывает интерфейс выбора файла и вендора в главном окне"""
        # Очищаем окно
        for w in self.winfo_children():
            w.destroy()

        self.parent.geometry("600x400")
        # Центрируем окно
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.parent.geometry(f"+{x}+{y}")

        # Заголовок
        ttk.Label(self, text="Выберите файл прайс-листа и поставщика",
                  font="-size 12 -weight bold").pack(pady=20)

        # Фрейм для выбора файла
        file_frame = ttk.Frame(self)
        file_frame.pack(fill=X, padx=50, pady=10)

        ttk.Label(file_frame, text="Файл прайс-листа:").pack(anchor=W)

        file_selection_frame = ttk.Frame(file_frame)
        file_selection_frame.pack(fill=X, pady=5)

        self.file_path_var = ttk.StringVar(value="Файл не выбран")
        file_label = ttk.Label(file_selection_frame, textvariable=self.file_path_var,
                               style="secondary.TLabel")
        file_label.pack(side=LEFT, fill=X, expand=True)

        ttk.Button(file_selection_frame, text="Выбрать файл",
                   command=self._select_file).pack(side=RIGHT, padx=(10, 0))

        # Фрейм для выбора вендора
        vendor_frame = ttk.Frame(self)
        vendor_frame.pack(fill=X, padx=50, pady=10)

        ttk.Label(vendor_frame, text="Поставщик:").pack(anchor=W)

        vendor_selection_frame = ttk.Frame(vendor_frame)
        vendor_selection_frame.pack(fill=X, pady=5)

        # Получаем список вендоров из БД
        vendors = crud.list_vendors()
        vendor_names = [vendor.name for vendor in vendors]

        self.vendor_combobox = ttk.Combobox(vendor_selection_frame, values=vendor_names, state="readonly")
        self.vendor_combobox.pack(side=LEFT, fill=X, expand=True)

        ttk.Button(vendor_selection_frame, text="Новый поставщик",
                   command=self._create_new_vendor).pack(side=RIGHT, padx=(10, 0))

        # Кнопка запуска
        self.start_button = ttk.Button(self, text="Начать парсинг",
                                       bootstyle=SUCCESS, command=self._start_parsing,
                                       state=DISABLED)
        self.start_button.pack(pady=20)

        # Кнопка выхода
        ttk.Button(self, text="Выход", bootstyle=DANGER,
                   command=self.parent.destroy).pack(pady=10)

        # Связываем проверку состояния кнопки
        self.file_path_var.trace('w', self._check_start_conditions)
        self.vendor_combobox.bind('<<ComboboxSelected>>', lambda e: self._check_start_conditions())

    def _start_parsing(self):
        """Запускает парсинг с выбранными параметрами"""
        file_path = self.file_path_var.get()
        vendor_name = self.vendor_combobox.get()

        # Переходим к основному интерфейсу парсера
        self._initialize_app(vendor_name, file_path, "", None)

    def _select_file(self):
        """Выбор файла через диалоговое окно"""
        file_path = filedialog.askopenfilename(
            title="Выберите файл прайс-листа",
            filetypes=[("Excel files", "*.xlsx *.xls *.xlsm *xlsb"), ("All files", "*.*")]
        )
        if file_path:
            self.file_path_var.set(file_path)

    def _create_new_vendor(self):
        """Создание нового поставщика"""
        vendor_name = simpledialog.askstring(
            "Новый поставщик",
            "Введите название поставщика:",
            parent=self
        )
        if vendor_name:
            # Добавляем вендора в БД
            crud.add_vendor(vendor_name)
            # Обновляем список в комбобоксе
            vendors = crud.list_vendors()
            vendor_names = [vendor.name for vendor in vendors]
            self.vendor_combobox['values'] = vendor_names
            self.vendor_combobox.set(vendor_name)
            self._check_start_conditions()

    def _check_start_conditions(self, *args):
        """Проверяет, можно ли запускать парсинг"""
        file_selected = self.file_path_var.get() != "Файл не выбран"
        vendor_selected = bool(self.vendor_combobox.get())

        if file_selected and vendor_selected:
            self.start_button.config(state=NORMAL)
        else:
            self.start_button.config(state=DISABLED)

    def _initialize_app(self, vendor, file_in, file_prefix: str = "", config_name: str | None = None):
        """Инициализирует основное приложение с переданными параметрами"""

        self.parent.geometry("1200x750")
        self.update_idletasks()
        x = (self.winfo_screenwidth() - self.winfo_width()) // 2
        y = (self.winfo_screenheight() - self.winfo_height()) // 2
        self.parent.geometry(f"+{x}+{y}")

        self.file_path = Path(file_in)
        self.output_file = Path(Path(file_prefix) / Path(self.file_path.stem + '.xlsx'))
        self.config_name = config_name
        # if not config_name:
        #     self.config_name = f"Единый [{vendor}]"
        # else:
        #     self.config_name = f"{config_name} [{vendor}]"

        # crud.add_role("Наименование", required=True)
        # crud.add_role("Закупочная цена", required=True)
        # crud.add_role("Артикул", required=True)
        # crud.add_role("Остаток", required=True)
        # crud.add_role("Квант", required=False)
        # crud.add_role("Бренд", required=False)
        # crud.add_role("РРЦ", required=False)

        self.VENDOR = vendor

        crud.add_vendor(self.VENDOR)

        self.ROLES = crud.list_roles()

        self.CONFIG = crud.load_config_by_name(self.config_name, vendor_name=vendor)
        print(self.CONFIG)
        try:
            self.quantum_config = self.CONFIG.get('quantum_config')
            print("Quantum config found in config file.")
            #self._update_table()
        except Exception as e:
            traceback.print_exc()
            print("Quantum config not found in config file.")
            self.quantum_config = None

        self.df_raw = read_excel_safe(self.file_path)
        self.df = None
        self.df_filtered = None
        self.header_row = None

        self.preview_tree = None
        self.role_comboboxes = {}
        self.tree = None
        self.preview_tree_bottom = None
        self.preview_visible = False

        self._build_header_selector()

    # ----------------- Этап 1: выбор шапки -----------------
    def _auto_detect_header_row(self):
        """Автоматически определяет строку заголовка на основе существующего маппинга или ключевых слов"""

        # Если есть конфиг с маппингом - используем его
        if self.CONFIG and 'roles_mapping' in self.CONFIG:
            roles_mapping = self.CONFIG['roles_mapping']
            expected_columns = set(roles_mapping.values())

            # Проверяем строки вокруг сохраненной строки заголовка
            saved_header_row = self.CONFIG.get('header_row')
            if saved_header_row is not None:
                check_rows = [saved_header_row - 1, saved_header_row, saved_header_row + 1]
            else:
                check_rows = range(10)  # проверяем первые 10 строк

            best_match_row = None
            best_match_score = 0

            for row_idx in check_rows:
                if row_idx < 0 or row_idx >= len(self.df_raw):
                    continue

                try:
                    # Получаем заголовки из этой строки
                    header_row_data = self.df_raw.iloc[row_idx:row_idx + 1]
                    headers = header_row_data.infer_objects(copy=False).fillna("").astype(str).agg(
                        lambda col: " ".join([v.strip() for v in col if v.strip()]), axis=0
                    )

                    # Сравниваем с ожидаемыми колонками
                    current_columns = set(headers)
                    match_score = len(expected_columns.intersection(current_columns))

                    if match_score > best_match_score:
                        best_match_score = match_score
                        best_match_row = row_idx

                except Exception as e:
                    print(f"Ошибка при проверке строки {row_idx}: {e}")
                    continue

            # Если нашли хорошее совпадение (хотя бы 2 колонки), возвращаем эту строку
            if best_match_score >= 2:
                print(f"Автоопределение по конфигу: строка {best_match_row} (совпадений: {best_match_score})")
                return best_match_row

        # Если нет конфига или автоопределение по конфигу не сработало - используем ключевые слова
        return self._auto_detect_header_by_keywords()

    def _auto_detect_header_by_keywords(self):
        """Автоматически определяет строку заголовка по ключевым словам"""

        # Ключевые слова для поиска в заголовках (в порядке приоритета)
        keywords = [
            # Основные обязательные поля
            ['наименование', 'номенклатура', 'название', 'товар', 'name', 'product', 'description'],
            ['артикул', 'арт', 'код', 'article', 'sku', 'code'],
            ['цена', 'стоимость', 'закуп', 'прайс', 'price', 'cost'],
            ['остаток', 'склад', 'наличие', 'кол-во', 'количество', 'stock', 'quantity', 'available'],
            ['бренд', 'производитель', 'brand', 'manufacturer'],
            ['ррц', 'рц', 'цр', 'рекомендованная', 'recommended', 'rrp'],
            # Дополнительные поля
            ['ед', 'единица', 'измерен', 'unit', 'measure'],
            ['категория', 'группа', 'category', 'group'],
            ['страна', 'происхожден', 'country', 'origin'],
            ['вес', 'габарит', 'weight', 'dimension']
        ]

        best_match_row = None
        best_match_score = 0
        best_row_content = None

        # Проверяем первые 20 строк
        for row_idx in range(min(20, len(self.df_raw))):
            try:
                # Получаем данные строки
                row_data = self.df_raw.iloc[row_idx:row_idx + 1]
                headers = row_data.infer_objects(copy=False).fillna("").astype(str).agg(
                    lambda col: " ".join([v.strip() for v in col if v.strip()]), axis=0
                )

                # Подсчитываем score для этой строки
                current_score = 0
                found_keywords = []

                for header in headers:
                    header_lower = header.lower().strip()
                    if not header_lower:  # пропускаем пустые заголовки
                        continue

                    # Проверяем каждую группу ключевых слов
                    for i, keyword_group in enumerate(keywords):
                        for keyword in keyword_group:
                            if keyword in header_lower:
                                # Даем больше очков за более приоритетные группы
                                score = len(keywords) - i
                                current_score += score
                                found_keywords.append((keyword, header))
                                break  # выходим из внутреннего цикла после первого совпадения в группе

                # Отладочная информация
                # if current_score > 0:
                #     print(f"Строка {row_idx}: score={current_score}, keywords={found_keywords}")

                # Обновляем лучший результат
                if current_score > best_match_score:
                    best_match_score = current_score
                    best_match_row = row_idx
                    best_row_content = list(headers)

            except Exception as e:
                #print(f"Ошибка при анализе строки {row_idx}: {e}")
                continue

        # Устанавливаем порог для минимального score
        min_acceptable_score = 3

        if best_match_score >= min_acceptable_score:
            #print(f"Автоопределение по ключевым словам: строка {best_match_row}")
            #print(f"Score: {best_match_score}, Заголовки: {best_row_content}")
            return best_match_row
        else:
            # print(
            #     f"Автоопределение по ключевым словам не удалось. Лучший score: {best_match_score} (требуется {min_acceptable_score})")
            return None

    def _auto_assign_roles(self, headers):
        """Автоматически назначает роли колонкам на основе ключевых слов"""
        # Словарь ключевых слов для каждой роли (в порядке приоритета)
        role_keywords = {
            "Наименование": [
                "наименование", "номенклатура", "название", "товар", "name", "product"
            ],
            "Закупочная цена": [
                "цена", "стоимость", "закуп", "прайс", "price", "cost", "розница", "розничная"
            ],
            "Артикул": [
                "артикул", "арт", "код", "article", "sku", "code", "кодтовара", "кодпродукта"
            ],
            "Остаток": [
                "остаток", "склад", "наличие", "кол-во", "количество", "stock", "quantity", "available", "остатки"
            ],
            "Бренд": [
                "бренд", "производитель", "brand", "manufacturer", "фирма", "произв", "торговаямарка", "марка"
            ],
            "РРЦ": [
                "ррц", "рц", "цр", "рекомендованная", "recommended", "rrp", "мрц", "рекомендованнаяцена"
            ],
            "Квант": [
                "кратность", "квант"
            ],
            "_box_quantity": ["коробк", "коробке", "ящик", "box", "case", "упаковк"],
            "_block_quantity": ["блок", "блоке", "дисплей", "block", "display"]
        }

        assigned_mapping = {}
        used_columns = set()

        # Сначала назначаем обязательные роли
        required_roles = [role for role in self.ROLES if role.required]

        for role in required_roles:
            role_name = role.name
            if role_name not in role_keywords:
                continue

            best_column = None
            best_score = 0

            for column in headers:
                if column in used_columns:
                    continue

                column_lower = column.lower().strip()
                if not column_lower:
                    continue

                # Подсчитываем score для этой колонки
                score = 0
                for i, keyword in enumerate(role_keywords[role_name]):
                    if keyword in column_lower:
                        # Даем больше очков за более точные совпадения
                        score = len(role_keywords[role_name]) - i
                        break

                if score > best_score:
                    best_score = score
                    best_column = column

            if best_column and best_score > 0:
                assigned_mapping[role_name] = best_column
                used_columns.add(best_column)

        # Затем назначаем необязательные роли
        optional_roles = [role for role in self.ROLES if not role.required]

        for role in optional_roles:
            role_name = role.name
            if role_name not in role_keywords:
                continue

            best_column = None
            best_score = 0

            for column in headers:
                if column in used_columns:
                    continue

                column_lower = column.lower().strip()
                if not column_lower:
                    continue

                # Подсчитываем score для этой колонки
                score = 0
                for i, keyword in enumerate(role_keywords[role_name]):
                    if keyword in column_lower:
                        score = len(role_keywords[role_name]) - i
                        break

                if score > best_score:
                    best_score = score
                    best_column = column

            # Для необязательных ролей можно установить более низкий порог
            if best_column and best_score >= 2:  # Минимальный порог для необязательных
                assigned_mapping[role_name] = best_column
                used_columns.add(best_column)

        return assigned_mapping

    # Также можно добавить кнопку для принудительного автоопределения
    def _build_header_selector(self):
        for w in self.winfo_children(): w.destroy()

        # Верхняя панель с кнопкой автоопределения
        top_frame = ttk.Frame(self)
        top_frame.pack(fill=X, padx=10, pady=(10, 0))

        ttk.Label(top_frame, text="Выберите строку заголовка (клик по строке):",
                  font="-size 11 -weight bold").pack(side=LEFT, anchor=W)

        # Кнопка автоопределения - показываем всегда, а не только при наличии конфига
        ttk.Button(top_frame, text="Автоопределение", bootstyle=WARNING,
                   command=self._auto_select_header).pack(side=RIGHT, padx=(10, 0))

        frame = ttk.Frame(self)
        frame.pack(fill=BOTH, expand=YES, padx=10, pady=5)

        cols = [f"Кол {i + 1}" for i in range(len(self.df_raw.columns))]
        self.preview_tree = ttk.Treeview(frame, show="headings", columns=cols, height=20)
        for i, c in enumerate(cols):
            self.preview_tree.heading(c, text=c)
            self.preview_tree.column(c, width=120, anchor=W)
        vsb = ttk.Scrollbar(frame, orient=VERTICAL, command=self.preview_tree.yview)
        self.preview_tree.configure(yscroll=vsb.set)
        self.preview_tree.pack(side=LEFT, fill=BOTH, expand=YES)
        vsb.pack(side=LEFT, fill=Y)

        # Пытаемся автоматически определить строку заголовка
        auto_detected_row = self._auto_detect_header_row()

        for idx, row in self.df_raw.head(50).iterrows():
            self.preview_tree.insert("", END, values=[self._short_str(x) for x in row.tolist()], iid=str(idx))

            # --- если ранее был выбран заголовок или автоопределен ---
            try:
                saved_header_row = self.CONFIG.get("header_row", None)
            except:
                saved_header_row = None

            # Приоритет: автоопределенная строка > сохраненная строка
            row_to_select = auto_detected_row if auto_detected_row is not None else saved_header_row

            if row_to_select is not None:
                try:
                    if str(row_to_select) in self.preview_tree.get_children():
                        self.preview_tree.selection_set(str(row_to_select))
                        self.preview_tree.see(str(row_to_select))

                        if auto_detected_row is not None and auto_detected_row == idx:
                            self.info_label = ttk.Label(
                                self,
                                text=f"Автоопределена строка {auto_detected_row + 1} (на основе сохраненных настроек)",
                                bootstyle=SUCCESS
                            )
                            self.info_label.pack(pady=5)

                except Exception as e:
                    print(f"[WARN] Ошибка при восстановлении выделения: {e}")

        self.preview_tree.bind("<<TreeviewSelect>>", self._on_header_row_select)

        if not hasattr(self, 'info_label'):
            self.info_label = ttk.Label(self, text="Нажмите на строку, где располагается заголовок", bootstyle=INFO)
            self.info_label.pack(pady=5)

    def _auto_select_header(self):
        """Принудительное автоопределение строки заголовка"""
        auto_detected_row = self._auto_detect_header_row()
        if auto_detected_row is not None:
            # Выделяем найденную строку
            if str(auto_detected_row) in self.preview_tree.get_children():
                self.preview_tree.selection_set(str(auto_detected_row))
                self.preview_tree.see(str(auto_detected_row))

                # Определяем тип автоопределения для сообщения
                if self.CONFIG and 'roles_mapping' in self.CONFIG:
                    message_type = "на основе сохраненных настроек"
                else:
                    message_type = "по ключевым словам"

                self.info_label.config(
                    text=f"Автоопределена строка {auto_detected_row + 1} ({message_type})",
                    bootstyle=SUCCESS
                )
                ToastNotification(
                    title="Автоопределение",
                    message=f"Выбрана строка {auto_detected_row + 1} ({message_type})",
                    bootstyle=SUCCESS
                ).show_toast()
        else:
            self.info_label.config(
                text="Не удалось автоматически определить строку заголовка",
                bootstyle=WARNING
            )
            ToastNotification(
                title="Автоопределение",
                message="Не удалось автоматически определить строку заголовка",
                bootstyle=WARNING
            ).show_toast()

    def _short_str(self, v, maxlen=40):
        s = "" if pd.isna(v) else str(v)
        return s if len(s) <= maxlen else s[:maxlen - 3] + "..."

    def _on_header_row_select(self, event):
        sel = self.preview_tree.selection()
        if not sel:
            return
        self.header_row = int(sel[0])
        self.info_label.config(text=f"Вы выбрали строку {self.header_row + 1}")
        if not hasattr(self, "_continue_btn"):
            self._continue_btn = ttk.Button(self, text="Продолжить", bootstyle=SUCCESS, command=self._apply_header)
            self._continue_btn.pack(pady=8)

    # ----------------- Этап 2: строим второй экран -----------------
    def _apply_header(self):
        # объединяем строки шапки
        header_part = self.df_raw.iloc[self.header_row:self.header_row + 1]
        # Исправляем предупреждение и здесь
        headers = header_part.fillna("").astype(str).agg(
            lambda col: " ".join([v.strip() for v in col if v.strip()]), axis=0
        ).infer_objects(copy=False)  # Добавляем infer_objects()

        self.df = self.df_raw.iloc[self.header_row + 1:].copy()
        self.df.columns = headers
        self.df.dropna(how="all", inplace=True)
        self.df.reset_index(drop=True, inplace=True)

        # ---------------- фильтруем колонки без названия ----------------
        valid_columns = [c for c in self.df.columns if c.strip() != ""]
        self.df = self.df[valid_columns]

        # чистим окно и строим интерфейс выбора ролей
        for w in self.winfo_children(): w.destroy()

        container = ttk.Frame(self)
        container.pack(fill=BOTH, expand=YES, padx=8, pady=8)

        # Верхняя панель: заголовок и кнопки
        top_header_frame = ttk.Frame(container)
        top_header_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(top_header_frame, text="Роли (назначьте столбцы):",
                  font="-size 11 -weight bold").pack(side=LEFT, anchor=W)

        # Кнопки справа
        buttons_frame = ttk.Frame(top_header_frame)
        buttons_frame.pack(side=RIGHT, anchor=E)

        # Добавляем кнопку автоназначения ролей
        btn_auto_assign = ttk.Button(buttons_frame, text="Автоназначение ролей", bootstyle=INFO,
                                     command=self._auto_assign_roles_ui)
        btn_auto_assign.pack(side=LEFT, padx=(10, 0))

        btn_quick_save = ttk.Button(buttons_frame, text="Сохраненить результат в файл", bootstyle=WARNING,
                                    command=self._quick_save)
        btn_quick_save.pack(side=LEFT, padx=(10, 0))

        btn_save = ttk.Button(buttons_frame, text="Сохранить настройки и закрыть окно", bootstyle=SUCCESS,
                              command=self._save_roles)
        btn_save.pack(side=LEFT, padx=(10, 0))

        # Основной контент с ролями и предпросмотром
        main_content = ttk.Frame(container)
        main_content.pack(fill=BOTH, expand=YES)

        # Верхняя часть - роли
        top_frame = ttk.Frame(main_content)  # начальная высота
        top_frame.place(x=0, y=0, relwidth=1, height=300)  # используем place
        self.top_frame = top_frame  # сохраняем ссылку для доступа из методов перетаскивания

        self.role_comboboxes = {}
        self.role_previews = {}
        self.available_columns = list(self.df.columns)

        # Создаем скроллируемую область для ролей
        roles_canvas = ttk.Canvas(top_frame)
        roles_scroll = ttk.Scrollbar(top_frame, orient=VERTICAL, command=roles_canvas.yview)

        roles_frame = ttk.Frame(roles_canvas)

        roles_frame.bind("<Configure>", lambda e: roles_canvas.configure(scrollregion=roles_canvas.bbox("all")))
        roles_canvas.create_window((0, 0), window=roles_frame, anchor="nw")
        roles_canvas.configure(yscrollcommand=roles_scroll.set)

        # Упаковываем канвас, скроллбар пока не упаковываем
        roles_canvas.pack(side=LEFT, fill=BOTH, expand=YES)

        # Функция для проверки необходимости скроллбара
        def check_scrollbar_needed(*args):
            roles_canvas.update_idletasks()
            content_height = roles_frame.winfo_reqheight()
            visible_height = roles_canvas.winfo_height()

            if content_height > visible_height:
                if not roles_scroll.winfo_ismapped():
                    roles_scroll.pack(side=RIGHT, fill=Y)
            else:
                if roles_scroll.winfo_ismapped():
                    roles_scroll.pack_forget()

        roles_canvas.bind("<Configure>", check_scrollbar_needed)
        roles_frame.bind("<Configure>", check_scrollbar_needed)

        # Автоматически назначаем роли, если это новый конфиг
        auto_assigned_mapping = None
        if not self.CONFIG or 'roles_mapping' not in self.CONFIG:
            auto_assigned_mapping = self._auto_assign_roles(self.df.columns)
            print(f"Автоназначенные роли: {auto_assigned_mapping}")

        quantum_row = None
        for role in self.ROLES:
            if role.name == "Квант":
                rowf = ttk.Frame(roles_frame)
                rowf.pack(fill=X, pady=4, padx=6)
                quantum_row = rowf

                ttk.Label(rowf, text=role.name, width=15, anchor=W).pack(side=LEFT)
                cmb = ttk.Combobox(rowf, values=["(не выбрано)"] + self.available_columns, width=30, bootstyle=INFO)
                cmb.set("(не выбрано)")

                if self.CONFIG and 'roles_mapping' in self.CONFIG:
                    m = self.CONFIG.get('roles_mapping')
                    cmb.set(m.get(role.name, "(не выбрано)"))
                if self.quantum_config:
                    print(f"Quantum config found: {self.quantum_config}")
                    m = self.quantum_config.get('quantum_column')
                    cmb.set(m)

                cmb.pack(side=LEFT, padx=(6, 0))
                cmb.bind("<<ComboboxSelected>>", partial(self._on_role_change, role, cmb))
                self.role_comboboxes[role] = cmb

                # Добавляем кнопку для расширенной настройки кванта
                ttk.Button(rowf, text="⚙", width=3, bootstyle=INFO,
                           command=partial(self._configure_quantum, cmb)).pack(side=LEFT, padx=(5, 0))
                continue
            rowf = ttk.Frame(roles_frame)
            rowf.pack(fill=X, pady=4, padx=6)
            ttk.Label(rowf, text=role.name, width=15, anchor=W).pack(side=LEFT)
            cmb = ttk.Combobox(rowf, values=["(не выбрано)"] + self.available_columns, width=30, bootstyle=INFO)
            cmb.set("(не выбрано)")

            # Приоритет: сохраненный конфиг > автоназначение
            if self.CONFIG and 'roles_mapping' in self.CONFIG:
                m = self.CONFIG.get('roles_mapping')
                cmb.set(m.get(role.name, "(не выбрано)"))
            elif auto_assigned_mapping and role.name in auto_assigned_mapping:
                cmb.set(auto_assigned_mapping[role.name])

            cmb.pack(side=LEFT, padx=(6, 0))
            cmb.bind("<<ComboboxSelected>>", partial(self._on_role_change, role, cmb))
            self.role_comboboxes[role] = cmb

        # Кастомный разделитель
        self.separator = ttk.Frame(main_content, height=8, style="secondary.TFrame")
        self.separator.place(x=0, y=300, relwidth=1, height=8)  # позиционируем разделитель

        # Нижняя часть - предпросмотр
        self.bottom_frame = ttk.LabelFrame(main_content, text="Предпросмотр данных")
        self.bottom_frame.place(x=0, y=308, relwidth=1, relheight=1)  # relheight будет корректироваться

        self.preview_visible = False
        self._drag_data = {"start_y": 0, "start_top_height": 0}

        # События для перетаскивания разделителя
        self.separator.bind("<ButtonPress-1>", self._on_separator_press)
        self.separator.bind("<B1-Motion>", self._on_separator_drag)
        self.separator.bind("<Enter>", lambda e: self.separator.configure(cursor="sb_v_double_arrow"))
        self.separator.bind("<Leave>", lambda e: self.separator.configure(cursor=""))

        roles_canvas.after(100, check_scrollbar_needed)

        self._update_table()

        # Показываем уведомление об автоназначении
        if auto_assigned_mapping:
            assigned_count = len([v for v in auto_assigned_mapping.values() if v != "(не выбрано)"])
            if assigned_count > 0:
                ToastNotification(
                    title="Автоназначение ролей",
                    message=f"Автоматически назначено {assigned_count} ролей. Проверьте и при необходимости скорректируйте.",
                    bootstyle=INFO,
                    duration=4000
                ).show_toast()

    def _configure_quantum(self, quantum_cmb):
        """Открывает диалог для настройки сложной логики кванта"""
        print(self.quantum_config)
        dialog = QuantumConfigDialog(self, self.available_columns, self.quantum_config)
        self.wait_window(dialog)

        if dialog.result:
            self.quantum_config = dialog.result
            # Автоматически выбираем колонку кванта в основном комбобоксе
            if self.quantum_config['quantum_column']:
                quantum_cmb.set(self.quantum_config['quantum_column'])
                self._update_available_columns()
                self._update_table()

            ToastNotification(
                title="Настройка кванта",
                message="Логика кванта настроена",
                bootstyle=SUCCESS
            ).show_toast()

    def _calculate_quantum_value(self, row):
        """Вычисляет значение кванта на основе конфигурации"""
        # if not self.quantum_config:
        #     return None

        try:
            quantum_col = self.quantum_config['quantum_column']
            if not quantum_col or quantum_col not in row:
                return 1

            unit = str(row[quantum_col]).strip().lower()
            if not unit:
                return 1

            # Ищем сопоставление для единицы измерения
            for unit_pattern, target_column in self.quantum_config['unit_mappings'].items():
                # if unit_pattern not in ["шт", "шт."]:
                #     print(f"...{unit_pattern} - {target_column}")
                if unit_pattern.lower() in unit or unit in unit_pattern.lower():
                    if target_column == "1":
                        return 1
                    elif target_column in row and pd.notna(row[target_column]):
                        try:
                            return float(row[target_column])
                        except (ValueError, TypeError):
                            pass

                    # Проверяем специальные колонки
                    if (unit_pattern.lower() in ['кор', 'коробка', 'кор.'] and
                            self.quantum_config['box_quantity_column'] in row):
                        try:
                            return float(row[self.quantum_config['box_quantity_column']])
                        except (ValueError, TypeError):
                            pass

                    if (unit_pattern.lower() in ['бл', 'блок', 'дисплейбокс'] and
                            self.quantum_config['block_quantity_column'] in row):
                        try:
                            return float(row[self.quantum_config['block_quantity_column']])
                        except (ValueError, TypeError):
                            pass

            # Если не нашли сопоставление, пробуем распарсить как число
            try:
                return float(unit)
            except (ValueError, TypeError):
                return 1  # Значение по умолчанию

        except Exception as e:
            print(f"Ошибка вычисления кванта: {e}")
            return 1

    def _auto_assign_roles_ui(self):
        """Автоматическое назначение ролей по ключевым словам (по кнопке)"""
        auto_assigned_mapping = self._auto_assign_roles(self.df.columns)

        if not auto_assigned_mapping:
            ToastNotification(
                title="Автоназначение",
                message="Не удалось автоматически назначить роли",
                bootstyle=WARNING
            ).show_toast()
            return

        # Применяем автоназначенные роли к комбобоксам
        assigned_count = 0
        for role, cmb in self.role_comboboxes.items():
            role_name = role.name
            if role_name in auto_assigned_mapping:
                cmb.set(auto_assigned_mapping[role_name])
                assigned_count += 1

        # Обновляем доступные колонки и таблицу
        self._update_available_columns()
        self._update_table()

        ToastNotification(
            title="Автоназначение ролей",
            message=f"Назначено {assigned_count} ролей автоматически",
            bootstyle=SUCCESS
        ).show_toast()

    # Добавляем методы для перетаскивания разделителя
    def _on_separator_press(self, event):
        """Начало перетаскивания разделителя"""
        self._drag_data = {
            "start_y": event.y_root,
            "start_top_height": self.top_frame.winfo_height()
        }

    def _on_separator_drag(self, event):
        """Перетаскивание разделителя"""
        if not hasattr(self, '_drag_data'):
            return

        # Вычисляем дельту от начальной точки
        delta = event.y_root - self._drag_data["start_y"]

        # Новая высота верхней части
        new_top_height = max(100, self._drag_data["start_top_height"] + delta)

        # Обновляем геометрию всех элементов
        self.top_frame.place_configure(height=new_top_height)
        self.separator.place_configure(y=new_top_height)

        # Вычисляем высоту для нижней части
        main_height = self.top_frame.master.winfo_height()
        bottom_height = max(100, main_height - new_top_height - 8)  # 8 - высота разделителя

        self.bottom_frame.place_configure(y=new_top_height + 8, relheight=1, height=bottom_height)

        # Обновляем отображение
        self.update_idletasks()

    # ----------------- обновление доступных колонок -----------------
    def _update_available_columns(self):
        """Обновляет список доступных колонок для всех комбобоксов"""
        # Собираем уже выбранные колонки
        selected_columns = set()
        for role, cmb in self.role_comboboxes.items():
            selected_value = cmb.get()
            if selected_value != "(не выбрано)":
                selected_columns.add(selected_value)

        # Формируем список доступных колонок
        available_columns = ["(не выбрано)"]

        # Добавляем все колонки, кроме уже выбранных
        for column in self.df.columns:
            if column not in selected_columns:
                available_columns.append(column)

        # Обновляем все комбобоксы
        for role, cmb in self.role_comboboxes.items():
            current_value = cmb.get()
            cmb['values'] = available_columns + [
                current_value] if current_value != "(не выбрано)" else available_columns
            # Сохраняем текущее значение, если оно еще доступно
            if current_value not in cmb['values']:
                cmb.set("(не выбрано)")

    # ----------------- обновление итоговой таблицы -----------------
    def _on_role_change(self, role, cmb, event=None):
        # Сначала обновляем доступные колонки
        self._update_available_columns()
        # Затем обновляем таблицу
        self._update_table()

    def _update_table(self):
        # получаем выбранные роли -> колонки
        mapping = {role.name: cmb.get() for role, cmb in self.role_comboboxes.items() if cmb.get() != "(не выбрано)"}
        columns = list(mapping.values())
        headers = list(mapping.keys())

        # обрабатываем данные
        if columns:
            try:
                self.df_filtered = self.df[columns].copy()
            except:
                self.CONFIG = None
                self._apply_header()
            # ключевые колонки
            price_col = mapping.get("Закупочная цена")
            name_col = mapping.get("Наименование")
            stock_col = mapping.get("Остаток")

            # фильтр по названию
            if name_col:
                try:
                    self.df_filtered = self.df_filtered[
                        self.df_filtered[name_col].notna() & (self.df_filtered[name_col].astype(str).str.strip() != "")]
                except KeyError as e:
                    print(e)

            # фильтр по цене
            def valid_price(v):
                if pd.isna(v):
                    return False
                if isinstance(v, (int, float)):
                    return True
                s = str(v).strip()
                # ищем число внутри строки
                match = re.search(r"\d+(\.\d+)?", s)
                if not match:
                    return False
                # ограничиваем общую длину до 10 символов (чтобы исключить длинный текст)
                return len(s) <= 10

            if price_col:
                try:
                    self.df_filtered = self.df_filtered[self.df_filtered[price_col].apply(valid_price)]
                except KeyError as e:
                    print(e)

            # Нормализация остатков
            if stock_col and stock_col in self.df_filtered.columns:
                self.df_filtered[stock_col] = self.df_filtered[stock_col].apply(normalize_stock_value)

            mapping = {role.name: cmb.get() for role, cmb in self.role_comboboxes.items() if
                       cmb.get() != "(не выбрано)"}
            quantum_col = mapping.get("Квант")

            if quantum_col and self.quantum_config and quantum_col == self.quantum_config['quantum_column']:
                # Применяем сложную логику для кванта
                print("Применяем сложную логику для кванта...")
                self.df_filtered[quantum_col] = self.df.apply(self._calculate_quantum_value, axis=1)
            elif quantum_col:
                # Стандартная обработка кванта
                try:
                    self.df_filtered[quantum_col] = pd.to_numeric(self.df_filtered[quantum_col], errors='coerce')
                except:
                    self.df_filtered[quantum_col] = 1

            # переименовываем колонки на роли
            self.df_filtered.columns = headers
            self.df_filtered["Поставщик"] = self.VENDOR

            # Управление видимостью предпросмотра
            if columns:  # если есть назначенные роли
                if not self.preview_visible:
                    self.preview_visible = True
                    self._create_preview()
                else:
                    self._create_preview()  # обновляем существующий
            else:  # если нет назначенных ролей
                if self.preview_visible:
                    # Скрываем предпросмотр
                    for widget in self.bottom_frame.winfo_children():
                        widget.destroy()
                    self.preview_visible = False
                self.df_filtered = None
                return

        # Обновляем компоновку
        self.update_idletasks()

    def _create_preview(self):
        # Очищаем предпросмотр
        for widget in self.bottom_frame.winfo_children():
            widget.destroy()

        # Создаем таблицу предпросмотра с прокруткой
        tree_frame = ttk.Frame(self.bottom_frame)
        tree_frame.pack(fill=BOTH, expand=YES, padx=5, pady=5)

        self.preview_tree_bottom = ttk.Treeview(tree_frame, show="headings", height=15)

        # Настраиваем колонки
        mapping = {role.name: cmb.get() for role, cmb in self.role_comboboxes.items() if cmb.get() != "(не выбрано)"}
        columns = list(mapping.values())
        columns.append("Поставщик")
        headers = list(mapping.keys())
        headers.append("Поставщик")

        self.preview_tree_bottom["columns"] = columns
        for c, h in zip(columns, headers):
            self.preview_tree_bottom.heading(c, text=h)
            self.preview_tree_bottom.column(c, width=120, anchor=W)

        # Заполняем данными
        if columns and hasattr(self, 'df_filtered') and self.df_filtered is not None:
            for _, row in self.df_filtered.head(100).iterrows():
                self.preview_tree_bottom.insert("", END, values=list(row))

        # Добавляем скроллбары
        prev_vsb = ttk.Scrollbar(tree_frame, orient=VERTICAL, command=self.preview_tree_bottom.yview)
        # prev_hsb = ttk.Scrollbar(tree_frame, orient=HORIZONTAL, command=self.preview_tree_bottom.xview)
        self.preview_tree_bottom.configure(yscroll=prev_vsb.set)  # , xscroll=prev_hsb.set)

        self.preview_tree_bottom.pack(side=LEFT, fill=BOTH, expand=YES)
        prev_vsb.pack(side=RIGHT, fill=Y)
        # prev_hsb.pack(side=BOTTOM, fill=X)

    # ----------------- сохранение -----------------
    def _save_roles(self):
        mapping = {role.name: cmb.get() for role, cmb in self.role_comboboxes.items() if cmb.get() != "(не выбрано)"}
        print(self.quantum_config)
        crud.save_config(
            config_name=self.config_name,
            vendor_name=self.VENDOR,
            header_row=self.header_row,
            roles_mapping=mapping,
            quantum_config=self.quantum_config
        )
        #to_excel_with_role_widths(self.df_filtered, self.output_file)
        ToastNotification(title="Сохранено", message=f"Настройки для {self.VENDOR} записаны в БД",
                          bootstyle=SUCCESS).show_toast()
        self.destroy()
        return self.df_filtered

    # ----------------- быстрое сохранение -----------------
    def _quick_save(self):
        """Быстрое сохранение результата в выбранный файл"""
        if not hasattr(self, 'df_filtered') or self.df_filtered is None or self.df_filtered.empty:
            ToastNotification(
                title="Ошибка",
                message="Нет данных для сохранения",
                bootstyle=DANGER
            ).show_toast()
            return

        # Запрашиваем файл у пользователя
        from tkinter import filedialog
        output_file = filedialog.asksaveasfilename(
            title="Сохранить результат как...",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )

        if not output_file:
            return  # Пользователь отменил сохранение

        try:
            # Сохраняем файл
            to_excel_with_role_widths(self.df_filtered, output_file)

            ToastNotification(
                title="Успешно",
                message=f"Файл сохранен: {output_file}",
                bootstyle=SUCCESS
            ).show_toast()

        except Exception as e:
            ToastNotification(
                title="Ошибка",
                message=f"Ошибка сохранения: {str(e)}",
                bootstyle=DANGER
            ).show_toast()


if __name__ == "__main__":
    app = PriceParserApp()
    app.mainloop()