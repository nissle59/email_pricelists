import re
import pandas as pd
from typing import Union


def normalize_stock_value(value) -> Union[int, str]:
    """
    Приводит значение остатка к единому числовому формату.
    Обрабатывает случаи: '>50', 'БОЛЕЕ50', '50+', '~50', 'около 50' и т.д.
    """
    if pd.isna(value):
        return 0

    if isinstance(value, (int, float)):
        return int(value)

    value_str = str(value).strip().upper()
    #value_str = re.sub(r'[ОКОЛО|ПРИМЕРНО|~|ПРИБЛИЗИТЕЛЬНО]', '', value_str, flags=re.IGNORECASE)
    #value_str = re.sub(r'[БОЛЕЕ|БОЛЬШЕ]', '', value_str, flags=re.IGNORECASE)
    value_str = value_str.replace(' ', '')

    numbers = re.findall(r'\d+', value_str)

    if numbers:
        stock_value = int(numbers[0])
        if any(symbol in value_str for symbol in ['БОЛЕЕ', 'БОЛЬШЕ', '>', '+', '≥']):
            return f"{stock_value}+"
        else:
            return stock_value
    else:
        if any(word in value_str for word in ['ЕСТЬ', 'ВНАЛИЧИИ', 'ДА', 'YES', '++']):
            return 1
        elif any(word in value_str for word in ['НЕТ', 'НЕТВНАЛИЧИИ', 'НЕТВ', 'ОТСУТСТВУЕТ', 'NO', '--', '---']):
            return 0
        else:
            return 0
