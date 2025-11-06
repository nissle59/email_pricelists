import re
import pandas as pd
from typing import Dict, Optional, List
from models import ParsingConfig


class AutoDetector:
    """Класс для автоматического определения заголовков и ролей"""

    def __init__(self):
        self.keywords = [
            ['наименование', 'номенклатура', 'название', 'товар', 'name', 'product', 'description'],
            ['артикул', 'арт', 'код', 'article', 'sku', 'code'],
            ['цена', 'стоимость', 'закуп', 'прайс', 'price', 'cost'],
            ['остаток', 'склад', 'наличие', 'кол-во', 'количество', 'stock', 'quantity', 'available'],
            ['бренд', 'производитель', 'brand', 'manufacturer'],
            ['ррц', 'рц', 'цр', 'рекомендованная', 'recommended', 'rrp'],
        ]

    def detect_header_row(self, df_raw: pd.DataFrame, config: Optional[ParsingConfig] = None) -> Optional[int]:
        """Автоматически определяет строку заголовка"""
        # Сначала пробуем по конфигу
        if config and hasattr(config, 'mappings'):
            detected_row = self._detect_by_config(df_raw, config)
            if detected_row is not None:
                return detected_row

        # Затем по ключевым словам
        return self._detect_by_keywords(df_raw)

    def _detect_by_config(self, df_raw: pd.DataFrame, config: ParsingConfig) -> Optional[int]:
        """Определение заголовка на основе сохраненного конфига"""
        mappings = config.mappings
        expected_columns = set(mappings.values())

        saved_header_row = getattr(config, 'header_row', None)
        check_rows = [saved_header_row - 1, saved_header_row, saved_header_row + 1] if saved_header_row else range(10)

        best_match_row = None
        best_match_score = 0

        for row_idx in check_rows:
            if row_idx < 0 or row_idx >= len(df_raw):
                continue

            try:
                header_row_data = df_raw.iloc[row_idx:row_idx + 1]
                headers = header_row_data.fillna("").astype(str).agg(
                    lambda col: " ".join([v.strip() for v in col if v.strip()]), axis=0
                )

                current_columns = set(headers)
                match_score = len(expected_columns.intersection(current_columns))

                if match_score > best_match_score:
                    best_match_score = match_score
                    best_match_row = row_idx

            except Exception:
                continue

        return best_match_row if best_match_score >= 2 else None

    def _detect_by_keywords(self, df_raw: pd.DataFrame) -> Optional[int]:
        """Определение заголовка по ключевым словам"""
        best_match_row = None
        best_match_score = 0

        for row_idx in range(min(20, len(df_raw))):
            try:
                row_data = df_raw.iloc[row_idx:row_idx + 1]
                headers = row_data.fillna("").astype(str).agg(
                    lambda col: " ".join([v.strip() for v in col if v.strip()]), axis=0
                )

                current_score = 0
                for header in headers:
                    header_lower = header.lower().strip()
                    if not header_lower:
                        continue

                    for i, keyword_group in enumerate(self.keywords):
                        for keyword in keyword_group:
                            if keyword in header_lower:
                                score = len(self.keywords) - i
                                current_score += score
                                break

                if current_score > best_match_score:
                    best_match_score = current_score
                    best_match_row = row_idx

            except Exception:
                continue

        return best_match_row if best_match_score >= 3 else None

    def auto_assign_roles(self, headers: List[str], roles: List) -> Dict[str, str]:
        """Автоматическое назначение ролей колонкам"""
        role_keywords = {
            "Наименование": ["наименование", "номенклатура", "название", "товар", "name", "product"],
            "Закупочная цена": ["цена", "стоимость", "закуп", "прайс", "price", "cost", "розница", "розничная"],
            "Артикул": ["артикул", "арт", "код", "article", "sku", "code", "кодтовара", "кодпродукта"],
            "Остаток": ["остаток", "склад", "наличие", "кол-во", "количество", "stock", "quantity", "available",
                        "остатки"],
            "Бренд": ["бренд", "производитель", "brand", "manufacturer", "фирма", "произв", "торговаямарка", "марка"],
            "РРЦ": ["ррц", "рц", "цр", "рекомендованная", "recommended", "rrp", "мрц", "рекомендованнаяцена"]
        }

        assigned_mapping = {}
        used_columns = set()

        # Сначала обязательные роли
        required_roles = [role for role in roles if role.required]
        for role in required_roles:
            role_name = role.name
            if role_name not in role_keywords:
                continue

            best_column = self._find_best_column_for_role(headers, role_keywords[role_name], used_columns)
            if best_column:
                assigned_mapping[role_name] = best_column
                used_columns.add(best_column)

        # Затем необязательные
        optional_roles = [role for role in roles if not role.required]
        for role in optional_roles:
            role_name = role.name
            if role_name not in role_keywords:
                continue

            best_column = self._find_best_column_for_role(headers, role_keywords[role_name], used_columns)
            if best_column:
                assigned_mapping[role_name] = best_column
                used_columns.add(best_column)

        return assigned_mapping

    def _find_best_column_for_role(self, headers: List[str], keywords: List[str], used_columns: set) -> Optional[str]:
        """Находит лучшую колонку для роли по ключевым словам"""
        best_column = None
        best_score = 0

        for column in headers:
            if column in used_columns:
                continue

            column_lower = column.lower().strip()
            if not column_lower:
                continue

            score = 0
            for i, keyword in enumerate(keywords):
                if keyword in column_lower:
                    score = len(keywords) - i
                    break

            if score > best_score:
                best_score = score
                best_column = column

        return best_column if best_score > 0 else None