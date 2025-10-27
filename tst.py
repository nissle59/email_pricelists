from pathlib import Path

import pandas as pd

from utils.convert_df import apply_parser_settings, to_excel_with_role_widths

role_widths = {
    "Наименование": 100,
    "Артикул": 18,
    "Цена": 16,
    "Остаток": 16,
    "(?) Бренд": 18,
    "(?) РРЦ": 16
}

fname = Path("ПрайсЛист_БИТ046184s (12).xlsx")
FILE_NAME = Path("sources/archive" / fname)
SETTINGS_NAME = Path("parser_settings" / Path(fname.stem + ".json"))

df_original = pd.read_excel(FILE_NAME, header=None)
df_filtered = apply_parser_settings(df_original, SETTINGS_NAME)
print(df_filtered.head())

to_excel_with_role_widths(df_filtered, FILE_NAME.stem+".xlsx", role_widths)
