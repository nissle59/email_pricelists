import imaplib
import email
import traceback
from email.header import decode_header
import os
import re
from datetime import datetime, timedelta
from email.utils import parseaddr
from typing import List, Dict, Optional, Union
import chardet

import settings
from crud import add_letter, add_attachment, list_letters_email_ids, list_vendors, add_vendor, list_email_filters, \
    get_vendor_name_by_id
from models import Letter, Attachment, Filters
from utils.imap import decode_folder_name


class YandexIMAPClient:
    def __init__(self, email: str, password: str, imap_server: str = "imap.yandex.ru", port: int = 993):
        self.db_scope: list[Filters] | None = None
        self.scope = None
        self.exluded_folders = [
            "Outbox",
            "Spam",
            "Trash",
            "\"Drafts|template\"",
            "Drafts",
            "Archive",
            "Sent"
        ]
        self.email = email
        self.password = password
        self.imap_server = imap_server
        self.port = port
        self.mail = None
        self.connected = False
        self.mark_as_read_on_download = False  # Флаг для отметки писем как прочитанных при скачивании
        self.email_ids_to_pass = []
        self.vendors = list_vendors()

    def set_folders_to_exculde(self, folders: List[str]):
        self.exluded_folders = folders

    def set_mark_as_read_on_download(self, mark: bool):
        """Установить флаг отметки писем как прочитанных только при успешном скачивании вложений"""
        self.mark_as_read_on_download = mark
        # print(f"Флаг 'mark_as_read_on_download' установлен в: {mark}")

    def set_credentials(self, email: str, password: str, imap_server: str = "imap.yandex.ru", port: int = 993):
        self.email = email
        self.password = password
        self.imap_server = imap_server
        self.port = port

    def connect(self) -> bool:
        """Подключение к IMAP серверу Яндекс"""
        try:
            self.mail = imaplib.IMAP4_SSL(self.imap_server, self.port)
            self.mail.login(self.email, self.password)
            self.connected = True
            print(f"Успешное подключение к {self.email}")
            return True
        except Exception as e:
            print(f"Ошибка подключения: {e}")
            return False

    def disconnect(self):
        """Отключение от сервера"""
        if self.mail and self.connected:
            self.mail.logout()
            self.connected = False
            print("Отключено от сервера")

    def list_folders(self) -> List[str]:
        """Получение списка папок"""
        if not self.connected:
            return []

        try:
            status, folders = self.mail.list()
            if status == "OK":
                return [folder.decode() for folder in folders]
        except Exception as e:
            print(f"Ошибка получения списка папок: {e}")
        return []

    def select_folder(self, folder: str = "INBOX") -> bool:
        """Выбор папки для работы"""
        if not self.connected:
            return False

        try:
            status, data = self.mail.select(folder, readonly=True)
            return status == "OK"
        except Exception as e:
            print(f"Ошибка выбора папки {folder}: {e}")
            return False

    def get_prices_by_senders(self, senders: List[str], limit_by_folder=None, days=None, since_date=None,
                              before_date=None,
                              folder="attachments", unread_only=False):
        results = {}
        out = []
        # print(f"Ищем письма для адресов: {', '.join(senders)}")
        # ГИБКОЕ УПРАВЛЕНИЕ: отмечать как прочитанные только при скачивании
        folders_data = self.list_folders()
        for folder_line in folders_data:
            # Извлекаем часть с названием папки (последняя часть после "|")
            parts = folder_line.split('"|"')
            if len(parts) > 1:
                folder_name = parts[-1].strip()
                if folder_name in self.exluded_folders:
                    continue
                decoded_name = decode_folder_name(folder_name)
                print(f"Ищем в папке: {decoded_name}")
                self.set_mark_as_read_on_download(False)
                self.select_folder(folder_name)
                # Поиск Excel файлов
                results.update(self.download_all_excel_files(
                    limit=limit_by_folder,
                    days=days,
                    since_date=since_date,
                    before_date=before_date,
                    folder=folder,
                    senders=senders,
                    unread_only=unread_only
                ))

        # Детальный вывод результатов
        if results:
            print("\n--- Детали скачивания ---")
            for email_id, info in results.items():
                if info['downloaded_files']:
                    print(f"\n✓ Письмо: {info['subject']}")
                    print(f"  От: {info['from']}")
                    print(f"  Дата: {info['date']}")
                    print(f"  Отмечено как прочитанное: {'Да' if info['marked_as_read'] else 'Нет'}")
                    for file_path in info['downloaded_files']:
                        out.append({
                            "subject": info['subject'],
                            "filename": file_path,
                            "date": info['date'],
                        })
                        file_size = os.path.getsize(file_path)
                        print(f"  📊 {os.path.basename(file_path)} ({file_size} bytes)")
        else:
            print("Excel файлы не найдены")
        return out


    def get_prices_by_scope(self, scope: dict, limit_by_folder=None, days=None, since_date=None,
                              before_date=None,
                              folder="attachments", unread_only=False):
        results = {}
        self.scope = scope
        out = []
        # print(f"Ищем письма для адресов: {', '.join(senders)}")
        # ГИБКОЕ УПРАВЛЕНИЕ: отмечать как прочитанные только при скачивании
        folders_data = self.list_folders()
        for folder_line in folders_data:
            # Извлекаем часть с названием папки (последняя часть после "|")
            parts = folder_line.split('"|"')
            if len(parts) > 1:
                folder_name = parts[-1].strip()
                if folder_name in self.exluded_folders:
                    continue
                decoded_name = decode_folder_name(folder_name)
                print(f"Ищем в папке: {decoded_name}")
                self.set_mark_as_read_on_download(False)
                self.select_folder(folder_name)
                # Поиск Excel файлов
                results.update(self.download_all_excel_files(
                    limit=limit_by_folder,
                    days=days,
                    since_date=since_date,
                    before_date=before_date,
                    folder=folder,
                    unread_only=unread_only
                ))

        # Детальный вывод результатов
        if results:
            print("\n--- Детали скачивания ---")
            for email_id, info in results.items():
                if info['downloaded_files']:
                    print(f"\n✓ Письмо: {info['subject']}")
                    print(f"  От: {info['from']}")
                    print(f"  Дата: {info['date']}")
                    print(f"  Отмечено как прочитанное: {'Да' if info['marked_as_read'] else 'Нет'}")
                    for file_path in info['downloaded_files']:
                        out.append({
                            "subject": info['subject'],
                            "filename": file_path,
                            "date": info['date'],
                        })
                        file_size = os.path.getsize(file_path)
                        print(f"  📊 {os.path.basename(file_path)} ({file_size} bytes)")
        else:
            print("Excel файлы не найдены")
        return out

    def search_emails(self, criteria: str = "ALL") -> List[str]:
        """Поиск писем по критериям"""
        print(f"Критерии поиска: {criteria}")
        out = []
        self.email_ids_to_pass = list_letters_email_ids()
        if not self.connected:
            return out

        try:
            status, messages = self.mail.search(None, criteria)
            if status == "OK":
                found = messages[0].split()
                for msg_id in found:
                    if int(msg_id) not in self.email_ids_to_pass:
                        out.append(msg_id)
            else:
                print(status)

        except Exception as e:
            print(f"Ошибка поиска писем: {e}")
        return out

    def search_emails_by_date(self, days: int = None, since_date: datetime = None, before_date: datetime = None,
                              unread_only: bool = False, senders: Union[str, List[str]] = None) -> List[str]:
        """Поиск писем по дате"""
        if not self.connected:
            return []

        def build_or_chain(terms):
            if len(terms) == 1:
                return f'(FROM "{terms[0]}")'
            return f'(OR {build_or_chain(terms[:-1])} (FROM "{terms[-1]}"))'

        try:
            date_criteria = ""
            if days:
                # Поиск за последние N дней
                since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")
                if since_date[0] == '0':
                    since_date = since_date[1:]
                date_criteria = f'SINCE {since_date}'
            elif since_date and before_date:
                since_date = since_date.strftime("%d-%b-%Y")
                if since_date[0] == '0':
                    since_date = since_date[1:]
                before_date = before_date.strftime("%d-%b-%Y")
                if before_date[0] == '0':
                    before_date = before_date[1:]
                # Поиск в диапазоне дат
                date_criteria = f'SINCE {since_date} BEFORE {before_date}'
            elif since_date:
                # Поиск с определенной даты
                since_date = since_date.strftime("%d-%b-%Y")
                if since_date[0] == '0':
                    since_date = since_date[1:]
                date_criteria = f'SINCE {since_date}'
            elif before_date:
                # Поиск до определенной даты
                before_date = before_date.strftime("%d-%b-%Y")
                if before_date[0] == '0':
                    before_date = before_date[1:]
                date_criteria = f'BEFORE {before_date}'

            # Критерии для отправителей
            sender_criteria = ""
            if self.scope:
                senders = []
                for vendor, emails in self.scope.items():
                    senders.extend(emails)
            if self.db_scope:
                senders = []
                for rule in self.db_scope:
                    senders.extend([sender.strip() for sender in rule.senders.split(';')])

            if senders:
                if isinstance(senders, str):
                    senders = [senders]

                sender_parts = []
                for sender in senders:
                    clean_sender = sender.replace('"', '\\"')
                    sender_parts.append(f'FROM "{clean_sender}"')

                if len(sender_parts) == 1:
                    sender_criteria = sender_parts[0]
                else:
                    sender_criteria = f'({build_or_chain(senders)})'
                    #sender_criteria = f'{" OR ".join(sender_parts)}'

            # Комбинируем все критерии
            criteria_parts = []
            if date_criteria:
                criteria_parts.append(date_criteria)
            if sender_criteria:
                criteria_parts.append(sender_criteria)
            if unread_only:
                criteria_parts.append('UNSEEN')

            if criteria_parts:
                if len(criteria_parts) == 1:
                    criteria = criteria_parts[0]
                else:
                    criteria = f'({" ".join(criteria_parts)})'
            else:
                criteria = "ALL"

            return self.search_emails(criteria)

        except Exception as e:
            print(f"Ошибка поиска писем по дате: {e}")
            return []

    def get_email_details(self, email_id: str, mark_as_read: bool = False) -> Dict:
        """Получение детальной информации о письме"""
        if not self.connected:
            return {}

        try:
            # =============================================================
            # БЛОК ОТМЕТКИ ПИСЕМ КАК ПРОЧИТАННЫХ
            # =============================================================
            if mark_as_read:
                # Этот вариант отметит письмо как прочитанное
                status, msg_data = self.mail.fetch(email_id, "(RFC822)")
                print(f"Письмо {email_id} будет отмечено как прочитанное")
            else:
                # Этот вариант НЕ отмечает письмо как прочитанное
                status, msg_data = self.mail.fetch(email_id, "(BODY.PEEK[])")
            # =============================================================

            if status != "OK":
                return {}

            email_body = msg_data[0][1]
            msg = email.message_from_bytes(email_body)

            # Декодирование заголовков
            subject = self._decode_header(msg["Subject"])
            from_ = self._decode_header(msg["From"])
            date = msg["Date"]

            email_info = {
                'id': email_id.decode() if isinstance(email_id, bytes) else str(email_id),
                'subject': subject,
                'from': from_,
                'date': date,
                'attachments': [],
                'excel_attachments': [],
                'body': '',
                'body_html': ''
            }

            # Обработка содержимого письма
            email_info.update(self._process_email_content(msg))

            return email_info

        except Exception as e:
            print(f"Ошибка получения письма {email_id}: {e}")
            return {}

    def _process_email_content(self, msg) -> Dict:
        """Обработка содержимого письма и вложений"""
        body = ""
        body_html = ""
        attachments = []
        excel_attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                # Текст письма
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    body = self._decode_payload(part) or body

                # HTML версия письма
                elif content_type == "text/html" and "attachment" not in content_disposition:
                    body_html = self._decode_payload(part) or body_html

                # Вложения
                elif "attachment" in content_disposition or part.get_filename():
                    filename = part.get_filename()
                    if filename:
                        filename = self._decode_header(filename)
                        payload = part.get_payload(decode=True)
                        if payload:
                            attachment_info = {
                                'filename': filename,
                                'content_type': content_type,
                                'payload': payload,
                                'size': len(payload)
                            }
                            attachments.append(attachment_info)

                            # Проверяем, является ли вложение Excel файлом
                            if self._is_excel_file(filename):
                                excel_attachments.append(attachment_info)
        else:
            # Простое письмо без вложений
            content_type = msg.get_content_type()
            if content_type == "text/plain":
                body = self._decode_payload(msg)
            elif content_type == "text/html":
                body_html = self._decode_payload(msg)

        return {
            'body': body,
            'body_html': body_html,
            'attachments': attachments,
            'excel_attachments': excel_attachments
        }

    def _is_excel_file(self, filename: str) -> bool:
        """Проверяет, является ли файл Excel документом"""
        excel_extensions = ['.xls', '.xlsx', '.xlsm', '.xlsb']
        file_ext = os.path.splitext(filename.lower())[1]
        return file_ext in excel_extensions

    def _decode_payload(self, part) -> str:
        """Декодирование payload с автоматическим определением кодировки"""
        try:
            payload = part.get_payload(decode=True)
            if not payload:
                return ""

            # Пробуем определить кодировку
            encoding = part.get_content_charset()
            if not encoding:
                # Автоопределение кодировки
                detected = chardet.detect(payload)
                encoding = detected.get('encoding', 'utf-8')

            # Список кодировок для попытки декодирования
            encodings_to_try = [encoding, 'utf-8', 'cp1251', 'koi8-r', 'iso-8859-1', 'windows-1251']

            for enc in encodings_to_try:
                try:
                    if enc:
                        return payload.decode(enc, errors='replace')
                except (UnicodeDecodeError, LookupError):
                    continue

            # Если все попытки неудачны, используем замену символов
            return payload.decode('utf-8', errors='replace')

        except Exception as e:
            print(f"Ошибка декодирования payload: {e}")
            return ""

    def _decode_header(self, header) -> str:
        """Декодирование заголовков email"""
        if header is None:
            return ""

        try:
            decoded_parts = decode_header(header)
            decoded_header = ""
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_header += part.decode(encoding, errors='replace')
                    else:
                        # Пробуем разные кодировки
                        try:
                            decoded_header += part.decode('utf-8', errors='replace')
                        except UnicodeDecodeError:
                            try:
                                decoded_header += part.decode('cp1251', errors='replace')
                            except UnicodeDecodeError:
                                decoded_header += part.decode('iso-8859-1', errors='replace')
                else:
                    decoded_header += part

            return decoded_header
        except Exception as e:
            print(f"Ошибка декодирования заголовка: {e}")
            return str(header) if header else ""

    def mark_email_as_read(self, email_id: str) -> bool:
        """Явно отметить письмо как прочитанное"""
        if not self.connected:
            return False

        try:
            # Используем FETCH с флагом \Seen для отметки как прочитанного
            status, response = self.mail.store(email_id, '+FLAGS', '\\Seen')
            if status == "OK":
                print(f"Письмо {email_id} отмечено как прочитанное")
                return True
            else:
                print(f"Не удалось отметить письмо {email_id} как прочитанное")
                return False
        except Exception as e:
            print(f"Ошибка при отметке письма {email_id} как прочитанного: {e}")
            return False

    def download_excel_attachments(self, email_info: Dict, download_folder: str = "unsort", email_rule: Filters | None = None) -> List[str]:
        """Скачивание только Excel вложений из письма"""
        download_folder = os.path.join("attachments", str(download_folder))
        downloaded_files = []
        excel_attachments = email_info.get('excel_attachments', [])

        if not excel_attachments:
            print("В письме нет Excel вложений")
            return downloaded_files

        for attachment in excel_attachments:
            try:
                filename = attachment['filename']
                payload = attachment['payload']

                if not filename or not payload:
                    continue

                # Очистка имени файла от недопустимых символов
                clean_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)

                approve_to_download: bool = True
                if email_rule:
                    if email_rule.filename_contains not in [None, ""]:
                        filename_contains = [r.strip() for r in email_rule.filename_contains.lower().split(";")]
                        app: list[bool] = []
                        for subj_c in filename_contains:
                            if clean_filename.lower().find(subj_c) < 0:
                                app.append(False)
                            else:
                                app.append(True)
                        if True not in app:
                            print(f"Несоответствие паттерну filename_contains: {email_rule.filename_contains}")
                            approve_to_download = False
                    if email_rule.filename_excludes not in [None, ""]:
                        filename_excludes = [r.strip() for r in email_rule.filename_excludes.lower().split(";")]
                        app: list[bool] = []
                        for subj_c in filename_excludes:
                            if clean_filename.lower().find(subj_c) >= 0:
                                app.append(False)
                            else:
                                app.append(True)
                        if False in app:
                            print(f"Несоответствие паттерну filename_excludes: {email_rule.filename_excludes}")
                            approve_to_download = False
                    if email_rule.extensions not in [None,""]:
                        app: list[bool] = []
                        for ext in email_rule.extensions.split(","):
                            ext = ext.strip()
                            if not clean_filename.lower().endswith(ext.lower()):
                                app.append(False)
                            else:
                                app.append(True)
                        if True not in app:
                            print(f"Несоответствие расширениям: {email_rule.extensions}")
                            approve_to_download = False

                if not approve_to_download:
                    print(f'Файл {clean_filename} не допущени к скачиванию')
                    continue

                filepath = os.path.join(download_folder, clean_filename)

                # Создаём папку, если её нет
                os.makedirs(os.path.dirname(filepath), exist_ok=True)

                # Проверяем, существует ли файл, и добавляем суффикс если нужно
                counter = 1
                original_filepath = filepath
                while os.path.exists(filepath):
                    name, ext = os.path.splitext(original_filepath)
                    filepath = f"{name}_{counter}{ext}"
                    counter += 1

                with open(filepath, 'wb') as f:
                    f.write(payload)

                downloaded_files.append(filepath)
                print(f"Скачан Excel файл: {clean_filename} ({len(payload)} bytes)")

            except Exception as e:
                print(f"Ошибка скачивания Excel файла {filename}: {e}")
                traceback.print_exc()

        # =============================================================
        # ОТМЕТКА ПИСЬМА КАК ПРОЧИТАННОГО ПОСЛЕ УСПЕШНОГО СКАЧИВАНИЯ
        # =============================================================
        if self.mark_as_read_on_download and downloaded_files:
            success = self.mark_email_as_read(email_info['id'])
            if success:
                print(f"✓ Письмо отмечено как прочитанное после успешного скачивания {len(downloaded_files)} файлов")
        # =============================================================

        return downloaded_files

    def get_emails_with_excel_attachments(self, email_ids: List[str] = None) -> List[Dict]:
        """Получение писем с Excel вложениями из списка ID"""
        if email_ids is None:
            email_ids = self.search_emails("ALL")

        emails_with_excel = []

        for email_id in email_ids:
            try:
                # Всегда используем BODY.PEEK[] при поиске писем, чтобы не отмечать как прочитанные
                email_info = self.get_email_details(email_id, mark_as_read=False)
                print(email_info.get('subject'), email_info.get('date'))
                if email_info and email_info.get('excel_attachments'):
                    print(
                        f"Найдено письмо с Excel вложением: [{email_info.get('date')}] {email_info.get('from')}: {email_info.get('subject')}")
                    emails_with_excel.append(email_info)
            except Exception as e:
                print(f"Ошибка обработки письма {email_id}: {e}")
                continue

        return emails_with_excel

    def search_unread_emails(self) -> List[str]:
        """Поиск непрочитанных писем"""
        if not self.connected:
            return []

        try:
            status, messages = self.mail.search(None, 'UNSEEN')
            if status == "OK":
                return messages[0].split()
        except Exception as e:
            print(f"Ошибка поиска непрочитанных писем: {e}")
        return []

    def search_emails_by_sender(self, senders: Union[str, List[str]], unread_only=False) -> List[str]:
        """Поиск писем по отправителю или списку отправителей"""
        if not self.connected:
            return []

        def build_or_chain(terms):
            if len(terms) == 1:
                return f'(FROM "{terms[0]}")'
            return f'(OR {build_or_chain(terms[:-1])} (FROM "{terms[-1]}"))'

        try:
            if isinstance(senders, str):
                senders = [senders]

            criteria_parts = []
            for sender in senders:
                # Экранируем специальные символы и добавляем в критерий
                clean_sender = sender.replace('"', '\\"')
                criteria_parts.append(f'FROM "{clean_sender}"')
                
            if unread_only:
                criteria_parts.append('UNSEEN')

            if len(criteria_parts) == 1:
                criteria = criteria_parts[0]
            else:
                criteria = build_or_chain(senders)

            # print(f"Критерии поиска по отправителям: {criteria}")
            return self.search_emails(criteria)

        except Exception as e:
            print(f"Ошибка поиска писем по отправителям: {e}")
            return []

    def download_all_excel_files(self,
                                 limit: int = None,
                                 days: int = None,
                                 since_date: datetime = None,
                                 before_date: datetime = None,
                                 folder: str = "attachments",
                                 unread_only: bool = False,
                                 senders: Union[str, List[str]] = None) -> Dict:  # Добавить этот параметр
        """
        Скачивает все Excel файлы из писем

        Args:
            limit: Ограничение по количеству писем (приоритет выше чем у дат)
            days: Поиск писем за последние N дней
            since_date: Поиск писем начиная с даты
            before_date: Поиск писем до даты
            folder: Папка для сохранения файлов
            unread_only: Искать только среди непрочитанных писем
            senders: Поиск по отправителю или списку отправителей
        """
        # Определяем стратегию поиска
        if limit:
            # Поиск по лимиту количества писем
            if unread_only or senders:
                # Используем комбинированный поиск
                email_ids = self.search_emails_by_sender(
                    unread_only=unread_only,
                    senders=senders
                )
            else:
                email_ids = self.search_emails("ALL")

            if email_ids:
                email_ids = email_ids[-limit:]  # Берем последние limit писем

            search_description = f"последние {limit} писем"
            if unread_only:
                search_description += " (только непрочитанные)"
            if senders:
                sender_list = senders if isinstance(senders, list) else [senders]
                search_description += f" (отправители: {', '.join(sender_list)})"
        else:
            # Поиск по дате с поддержкой непрочитанных и отправителей
            email_ids = self.search_emails_by_date(
                days=days,
                since_date=since_date,
                before_date=before_date,
                unread_only=unread_only,
                senders=senders
            )

            if days:
                search_description = f"письма за последние {days} дней"
            elif since_date and before_date:
                search_description = f"письма с {since_date} по {before_date}"
            elif since_date:
                search_description = f"письма с {since_date}"
            elif before_date:
                search_description = f"письма до {before_date}"
            else:
                search_description = "все письма"

            if unread_only:
                search_description += " (только непрочитанные)"
            if senders:
                sender_list = senders if isinstance(senders, list) else [senders]
                search_description += f" (отправители: {', '.join(sender_list)})"

        emails_with_excel = self.get_emails_with_excel_attachments(email_ids)

        total_downloaded = 0
        download_results = {}

        for i, email_info in enumerate(emails_with_excel, 1):
            raw_from = email_info['from'].strip()

            # Извлекаем первый валидный email из строки
            match = re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', raw_from)
            sender_email = match.group(0) if match else email_info['from']
            vendor_id = None
            email_rule = None
            if self.scope:
                for vendor, emails in self.scope.items():
                    if sender_email in emails:
                        if vendor not in [v.name for v in self.vendors]:
                            vendor_id = add_vendor(vendor).id
                        else:
                            vendor_id = [v.id for v in self.vendors if v.name == vendor][0]
                        folder = vendor_id
                        break

            if self.db_scope:
                for rule in self.db_scope:
                    if sender_email in rule.senders:
                        v_name = get_vendor_name_by_id(rule.vendor_id)
                        if v_name not in [v.name for v in self.vendors]:
                            vendor_id = add_vendor(v_name).id
                        else:
                            vendor_id = [v.id for v in self.vendors if v.name == v_name][0]
                        folder = vendor_id
                        email_rule: Filters = rule
                        break
            if vendor_id:
                approve_to_load: bool = True
                if email_rule:
                    if email_rule.subject_contains not in [None, ""]:
                        subject_contains = [r.strip() for r in email_rule.subject_contains.lower().split(";")]
                        app: list[bool] = []
                        for subj_c in subject_contains:
                            if email_info['subject'].lower().find(subj_c) < 0:
                                app.append(False)
                            else:
                                app.append(True)
                        if True not in app:
                            approve_to_load = False
                    if email_rule.subject_excludes not in [None, ""]:
                        subject_excludes = [r.strip() for r in email_rule.subject_excludes.lower().split(";")]
                        app: list[bool] = []
                        for subj_c in subject_excludes:
                            if email_info['subject'].lower().find(subj_c) >= 0:
                                app.append(False)
                            else:
                                app.append(True)
                        if False in app:
                            approve_to_load = False

                if not approve_to_load:
                    continue
                downloaded_files = self.download_excel_attachments(email_info, folder, email_rule)
                total_downloaded += len(downloaded_files)

                download_results[email_info['id']] = {
                    'subject': email_info['subject'],
                    'from': email_info['from'],
                    'date': email_info['date'],
                    'downloaded_files': downloaded_files,
                    'excel_count': len(email_info['excel_attachments']),
                    'marked_as_read': self.mark_as_read_on_download and bool(downloaded_files)
                }
                d = datetime.strptime(email_info['date'], "%a, %d %b %Y %H:%M:%S %z")


                letter: Letter = Letter(
                    letter_id=int(email_info['id']),
                    sender=sender_email,
                    subject=email_info['subject'],
                    date=d,
                    vendor_id=vendor_id
                )
                add_letter(letter)
                if downloaded_files:
                    for f in downloaded_files:
                        size = os.path.getsize(f)
                        a = Attachment(
                            letter_id=int(email_info['id']),
                            file_name=os.path.basename(f),
                            file_path=f,
                            size=size
                        )
                        add_attachment(a)

        return download_results
    
    def get_all_prices(self, limit_by_folder=None, days=None, since_date=None,
                              before_date=None,
                              folder="attachments", unread_only=False):
        if self.connect():
            try:
                results = {}
                self.db_scope: list[Filters] = list_email_filters()
                senders = []
                for rule in self.db_scope:
                    senders.extend(
                        rule.senders.split(';')
                    )
                out = []
                # print(f"Ищем письма для адресов: {', '.join(senders)}")
                # ГИБКОЕ УПРАВЛЕНИЕ: отмечать как прочитанные только при скачивании
                folders_data = self.list_folders()
                for folder_line in folders_data:
                    # Извлекаем часть с названием папки (последняя часть после "|")
                    parts = folder_line.split('"|"')
                    if len(parts) > 1:
                        folder_name = parts[-1].strip()
                        if folder_name in self.exluded_folders:
                            continue
                        decoded_name = decode_folder_name(folder_name)
                        print(f"Ищем в папке: {decoded_name}")
                        self.set_mark_as_read_on_download(False)
                        self.select_folder(folder_name)
                        # Поиск Excel файлов
                        results.update(self.download_all_excel_files(
                            limit=limit_by_folder,
                            days=days,
                            since_date=since_date,
                            before_date=before_date,
                            folder=folder,
                            unread_only=unread_only,
                            senders=senders
                        ))

                # Детальный вывод результатов
                if results:
                    print("\n--- Детали скачивания ---")
                    for email_id, info in results.items():
                        if info['downloaded_files']:
                            print(f"\n✓ Письмо: {info['subject']}")
                            print(f"  От: {info['from']}")
                            print(f"  Дата: {info['date']}")
                            print(f"  Отмечено как прочитанное: {'Да' if info['marked_as_read'] else 'Нет'}")
                            for file_path in info['downloaded_files']:
                                out.append({
                                    "subject": info['subject'],
                                    "filename": file_path,
                                    "date": info['date'],
                                })
                                file_size = os.path.getsize(file_path)
                                print(f"  📊 {os.path.basename(file_path)} ({file_size} bytes)")
                else:
                    print("Excel файлы не найдены")
                return out
            except Exception as e:
                print(f"Ошибка при обработке писем: {e}")
                return []
            finally:
                self.disconnect()


# Примеры использования
def main():
    # Настройки (замените на свои)
    EMAIL = "inaberu@yandex.ru"
    PASSWORD = "nmbknebkhqadsdzs"

    # Создание клиента
    client = YandexIMAPClient(EMAIL, PASSWORD)

    if client.connect():
        try:
            # ВАРИАНТ 1: Не отмечать письма как прочитанные (по умолчанию)
            client.set_mark_as_read_on_download(True)

            # Выбор папки входящие
            client.select_folder("INBOX")

            # Пример 1: Скачать Excel файлы без отметки как прочитанных
            print("=== Пример 1: Без отметки как прочитанных ===")
            results1 = client.download_all_excel_files(limit=5)

            # ВАРИАНТ 2: Отмечать письма как прочитанные только при успешном скачивании
            print("\n=== Пример 2: С отметкой как прочитанных при скачивании ===")
            client.set_mark_as_read_on_download(True)
            results2 = client.download_all_excel_files(limit=5, unread_only=True)

        except Exception as e:
            print(f"Общая ошибка: {e}")
        finally:
            client.disconnect()


def custom_search_example():
    """Пример кастомного поиска с гибким управлением отметкой прочитанных"""
    EMAIL = "inaberu@yandex.ru"
    PASSWORD = "nmbknebkhqadsdzs"
    """
- от email kormiltsev@technosite.ru берём вложения с расширением xlsx, в именах которых не содержится 'внешний заказ', либо вложение с любым расширением, если в его имени, либо теме содержится подстрока 'прайс'
- от khanova@technosite.ru берем вложения, только если в теме письма содержится подстрока 'прайс'
- от jtc2@autoopt.ru берем вложения, только если в теме письма есть подстрока 'прайс лист'
- от E.Maltseva@igr.ru берем все excel вложения
- от Kadyrmaeva@toys.inventive.ru берем все .xlsm/.xls/.xlsx, если в теме письма есть 'прайс' или 'новинки' или 'предложение'
- от order@mactak.ru берем вложения, если в теме письма есть 'прайс-лист'
- от 1c_mail@1toys.ru берем все вложения - эти ребята в фильтрации не нуждаются
- от sale@megalight.ru берем все вложения - фильтрация не нужна
    """
    client = YandexIMAPClient(EMAIL, PASSWORD)

    if client.connect():
        try:
            s = client.get_prices_by_senders(senders=["khanova@technosite.ru"], days=1, folder='temp')
        finally:
            client.disconnect()



s = settings.get_settings()

client = YandexIMAPClient(s.get('email_username'), s.get('email_password'), s.get('email_server', 'imap.yandex.ru'),
                          int(s.get('email_port', 993)))

if __name__ == "__main__":
    custom_search_example()
