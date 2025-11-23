import datetime
import json
import os
import shutil
import time
from pathlib import Path
from typing import Literal

import pandas as pd
import crud
from models import Filters, ParsingConfig
from utils.convert_df import apply_parser_settings, to_excel_with_role_widths
from utils.file_reader import read_excel_safe
from utils.paths import pm


def find_matching_config(filename, configs: list[ParsingConfig]):
    """Находит конфигурацию, подходящую для файла"""
    filename_lower = filename.lower()

    for config in configs:
        if config.filename_template.lower():
            pattern = config.filename_template.strip().lower()
        else:
            pattern = None
        if pattern and pattern in filename_lower:
            return config.id

    return None


def filter_emails_by_rule(
        emails: list,
        filter: Filters,
        start_dt: datetime.datetime | None = None,
        end_dt: datetime.datetime | None = None,
        limit: bool = False,
        ):
    bad = []
    configs = crud.list_configs_for_vendor_id(filter.vendor_id)
    cfgs = {}
    for cfg in configs:
        cfgs[cfg.id] = {"cfg": cfg, "items": []}
    for email in emails:
        # Проверка расширения
        if filter.extensions:
            ext_ok = any(email['filename'].lower().endswith(ext.strip().lower())
                         for ext in filter.extensions.split(','))
            if not ext_ok:
                bad.append(email)
                continue

        # Проверка темы
        if filter.subject_contains:
            subject_ok = any(keyword.strip().lower() in email['subject'].lower()
                             for keyword in filter.subject_contains.split(';'))
            if not subject_ok:
                bad.append(email)
                continue

        if filter.subject_excludes:
            subject_ex_ok = not any(keyword.strip().lower() in email['subject'].lower()
                                    for keyword in filter.subject_excludes.split(';'))
            if not subject_ex_ok:
                bad.append(email)
                continue

        # Проверка имени файла (содержит)
        if filter.filename_contains:
            filename_ok = any(keyword.strip().lower() in email['filename'].lower()
                              for keyword in filter.filename_contains.split(';'))
            if not filename_ok:
                bad.append(email)
                continue

        # Проверка имени файла (НЕ содержит)
        if filter.filename_excludes:
            filename_ex_ok = not any(keyword.strip().lower() in email['filename'].lower()
                                     for keyword in filter.filename_excludes.split(';'))
            if not filename_ex_ok:
                bad.append(email)
                continue

        for key, value in cfgs.items():
            filename_ok = value["cfg"].filename_template.strip().lower() in email['filename'].lower()
            if filename_ok:
                value["items"].append(email)

    if limit:
        for key, value in cfgs.items():
            try:
                value["items"] = [max(value["items"], key=lambda x: datetime.datetime.fromisoformat(x['date']))]
            except:
                value["items"] = []
    all_items = [item for value in cfgs.values() for item in value["items"]]
    if not all_items:
        return []
    if start_dt is not None and end_dt is not None:
        out = []
        for email in all_items:
            dt = datetime.datetime.fromisoformat(email['date'])
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
            if start_dt <= dt <= end_dt:
                out.append(email)
        return out
    return all_items


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Удаляет дубликаты по принципу: для одинаковых "Артикул" и "Поставщик"
    оставляет только строку с самой свежей "Дата"
    """
    if df.empty:
        return df

    # Проверяем наличие необходимых колонок
    required_columns = ['Артикул', 'Поставщик', 'Дата']
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        print(f"Предупреждение: отсутствуют колонки {missing_columns}. Пропускаем дедупликацию.")
        return df

    # ДИАГНОСТИКА
    print(f"Исходное количество строк: {len(df)}")
    print(f"Уникальных артикулов до: {df['Артикул'].nunique()}")
    print(f"Уникальных комбинаций артикул+поставщик до: {df[['Артикул', 'Поставщик']].drop_duplicates().shape[0]}")
    # Сортируем по дате в порядке убывания (самые свежие первыми)
    df_sorted = df.sort_values('Дата', ascending=False)

    # Удаляем дубликаты, оставляя первую запись (самую свежую) для каждой комбинации
    df_deduped = df_sorted.drop_duplicates(subset=['Артикул', 'Поставщик'], keep='first')

    # ДИАГНОСТИКА после
    print(f"Количество строк после: {len(df_deduped)}")
    print(f"Уникальных артикулов после: {df_deduped['Артикул'].nunique()}")
    print(
        f"Уникальных комбинаций артикул+поставщик после: {df_deduped[['Артикул', 'Поставщик']].drop_duplicates().shape[0]}")
    print(f"Удалено дубликатов: {len(df) - len(df_deduped)}")

    print(f"Удалено дубликатов: {len(df) - len(df_deduped)}")

    return df_deduped


def parse(
        start_dt: datetime.datetime | None = None,
        end_dt: datetime.datetime | None = None,
        limit: bool = False,
):
    vendors = crud.list_vendors()

    days = 365

    out_dfs = []
    for vendor in vendors:
        configs = crud.list_configs_for_vendor(vendor.name)
        if not vendor.active:
            print(f"Парсинг поставщика {vendor.name} отключен")
            continue
        emailfilter = crud.get_email_filter_by_vendor(vendor.id)
        emails_instances = crud.list_letters(vendor.id, days=days)
        emails = [
            {
                "subject": email.subject,
                "filename": a.file_name,
                "filepath": os.path.join(pm.get_user_data(), a.file_path),
                "date": email.date.isoformat()
            }
            for email in emails_instances
            for a in email.attachments
        ]
        filtered = filter_emails_by_rule(emails, emailfilter, start_dt, end_dt, limit)

        dfs = []
        for letter in filtered:
            source_path = Path(letter.get('filepath'))
            source_ext = source_path.suffix
            #letter_date = datetime.datetime.strptime(letter.get("date"), "%Y-%m-%d %H:%M")
            letter_date = datetime.datetime.fromisoformat(letter.get("date"))
            if not letter_date.tzinfo:
                letter_date = letter_date.replace(tzinfo=datetime.timezone.utc)
            utc_offset_sec = time.localtime().tm_gmtoff
            system_timezone = datetime.timezone(datetime.timedelta(seconds=utc_offset_sec))
            letter_date = letter_date.astimezone(system_timezone)
            cfg_id = find_matching_config(letter.get('filename'), configs)
            if cfg_id is not None:
                config_obj = next((c for c in configs if c.id == cfg_id), None)
                out_fname = f"[исходный] {vendor.name} - {config_obj.name} - {letter_date.strftime('%d.%m.%Y %H-%M')}" + source_ext
                if config_obj.save_original:
                    try:
                        if not source_path:
                            print("Путь к исходному файлу не указан")
                        elif not os.path.exists(source_path):
                            print(f"Исходный файл не существует: {source_path}")
                        else:
                            shutil.copy2(source_path, pm.save_file(out_fname, mode="source"))
                            print(f"Успешно скопировано: {source_path} -> {out_fname}")

                    except PermissionError:
                        print(f"Ошибка доступа при копировании файла")
                    except Exception as e:
                        print(f"Ошибка при копировании файла: {e}")
                try:
                    df_in = read_excel_safe(source_path)
                except FileNotFoundError:
                    print(f"Файл не найден: {source_path}")
                    continue
                try:
                    q_conf = json.loads(config_obj.quantum_config)
                except:
                    q_conf = None
                df_out = apply_parser_settings(df_in, config_obj, vendor.name, date=letter_date, quantum_config=q_conf)
                dfs.append({
                    "vendor_id": vendor.id,
                    "config_id": cfg_id,
                    "data": df_out
                })
        try:
            result_df = pd.concat([df["data"] for df in dfs])
            out_dfs.append(result_df)
        except:
            print("No data for " + vendor.name)

    # Объединяем все данные
    if out_dfs:
        out_df = pd.concat(out_dfs)

        # Удаляем дубликаты
        out_df = remove_duplicates(out_df)#.drop(['Дата'], axis=1)

        print(out_df)
        to_excel_with_role_widths(out_df, pm.save_file('Объединенный прайс.xlsx'))
        print('Done!')
    else:
        print("No data found")