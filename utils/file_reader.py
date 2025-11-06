from pathlib import Path
import pandas as pd


def read_excel_safe(file_path: str | Path) -> pd.DataFrame:
    # Сначала пробуем стандартный openpyxl
    engines = ['openpyxl', 'xlrd', 'calamine']

    for engine in engines:
        try:
            df = pd.read_excel(file_path, header=None, engine=engine)
            print(f"Успешно прочитали {file_path} через {engine}")
            return df
        except Exception as e:
            continue
    try:
        import xlwings as xw
        print("Пробуем через xlwings...")
        app = xw.App(visible=False)
        wb = xw.Book(file_path)
        sheet = wb.sheets[0]  # читаем первый лист
        data = sheet.used_range.value
        wb.close()
        app.quit()
        df = pd.DataFrame(data)
        return df
    except Exception as e2:
        print(f"Не удалось прочитать через xlwings: {e2}")
        raise
