import pandas as pd
import re
import json
from openpyxl.utils import get_column_letter
from openpyxl import load_workbook

def to_excel_with_role_widths(df: pd.DataFrame, filename: str, widths: dict | None = None):
    """
    Сохраняет DataFrame в Excel и устанавливает ширину колонок по ролям.

    Аргументы:
    - df: DataFrame
    - filename: путь к Excel файлу
    - widths: словарь {роль: ширина}
    """
    role_widths = {
        "Наименование": 100,
        "Артикул": 18,
        "Цена": 16,
        "Остаток": 16,
        "(?) Бренд": 18,
        "(?) РРЦ": 16
    }
    if not widths:
        widths = role_widths
    df.to_excel(filename, index=False)
    wb = load_workbook(filename)
    ws = wb.active

    for i, col in enumerate(df.columns, 1):
        width = widths.get(col, 15)  # если роль не в словаре, ставим ширину по умолчанию
        ws.column_dimensions[get_column_letter(i)].width = width

    wb.save(filename)


def apply_parser_settings(df_original: pd.DataFrame, settings_file: str) -> pd.DataFrame:
    """
    Применяет настройки парсинга к исходному DataFrame и возвращает отфильтрованный DataFrame.

    Параметры:
    - df_original: исходный DataFrame (все строки Excel)
    - settings_file: путь к JSON-файлу с настройками

    Возвращает:
    - df_filtered: DataFrame с колонками, переименованными в роли, только валидные записи
    """
    with open(settings_file, "r", encoding="utf-8") as f:
        settings = json.load(f)

    header_row = settings["header_row"]
    roles_mapping = settings["roles_mapping"]  # dict: роль -> исходная колонка

    # формируем DataFrame с правильными колонками
    df = df_original.copy()
    # объединяем шапку, если она многострочная
    header_part = df.iloc[header_row:header_row + 1]
    headers = header_part.fillna("").astype(str).agg(lambda col: " ".join([v.strip() for v in col if v.strip()]),
                                                     axis=0)
    df = df.iloc[header_row + 1:].copy()
    df.columns = headers
    df.dropna(how="all", inplace=True)
    df.reset_index(drop=True, inplace=True)

    # отбрасываем колонки без названия
    valid_columns = [c for c in df.columns if c.strip() != ""]
    df = df[valid_columns]

    # оставляем только колонки из ролей, которые есть в DataFrame
    used_columns = [roles_mapping[r] for r in roles_mapping if roles_mapping[r] in df.columns]
    df_filtered = df[used_columns].copy()

    # фильтрация строк ---------------------------------
    # имя и цена по ролям
    name_role = None
    price_role = None
    for r, col in roles_mapping.items():
        if r.lower() in ["наименование"]:
            name_role = r
        elif r.lower() in ["закупочная цена"]:
            price_role = r

    # переименуем колонки на роли
    df_filtered.columns = [r for r in roles_mapping if roles_mapping[r] in df_filtered.columns]

    # фильтруем по названию
    if name_role and name_role in df_filtered.columns:
        df_filtered = df_filtered[
            df_filtered[name_role].notna() & (df_filtered[name_role].astype(str).str.strip() != "")]

    # фильтруем по цене
    def valid_price(v):
        if pd.isna(v):
            return False
        if isinstance(v, (int, float)):
            return True
        s = str(v).strip()
        match = re.search(r"\d+(\.\d+)?", s)
        if not match:
            return False
        return len(s) <= 10  # ограничение по длине

    if price_role and price_role in df_filtered.columns:
        df_filtered = df_filtered[df_filtered[price_role].apply(valid_price)]

    return df_filtered