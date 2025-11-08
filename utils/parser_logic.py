import datetime
import json
import os
import shutil

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


def filter_emails_by_rule(emails: list, filter: Filters):
    filtered = []
    bad = []
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

        filtered.append(email)
    # print(json.dumps(filtered, indent=2, ensure_ascii=False))
    return filtered


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

    # Сортируем по дате в порядке убывания (самые свежие первыми)
    df_sorted = df.sort_values('Дата', ascending=False)

    # Удаляем дубликаты, оставляя первую запись (самую свежую) для каждой комбинации
    df_deduped = df_sorted.drop_duplicates(subset=['Артикул', 'Поставщик'], keep='first')

    print(f"Удалено дубликатов: {len(df) - len(df_deduped)}")

    return df_deduped


def parse(out_file: str = "price.xlsx", days=7):
    vendors = crud.list_vendors()
    configs = crud.list_all_configs()

    # print([c.name for c in configs])
    # return


    out_dfs = []
    for vendor in vendors:
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
                "date": email.date.strftime("%Y-%m-%d %H:%M")
            }
            for email in emails_instances
            for a in email.attachments
        ]
        filtered = filter_emails_by_rule(emails, emailfilter)

        dfs = []
        for letter in filtered:
            source_path = letter.get('filepath')
            letter_date = datetime.datetime.strptime(letter.get("date"), "%Y-%m-%d %H:%M")
            cfg_id = find_matching_config(letter.get('filename'), configs)
            if cfg_id is not None:
                config_obj = next((c for c in configs if c.id == cfg_id), None)
                out_fname = f"[исходный] {vendor.name} - {config_obj.name} - {letter_date.strftime('%d.%m.%Y %H-%M')}.xlsx"
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
        out_df = remove_duplicates(out_df).drop(['Дата'], axis=1)

        print(out_df)
        to_excel_with_role_widths(out_df, pm.save_file('Объединенный прайс.xlsx'))
        print('Done!')
    else:
        print("No data found")