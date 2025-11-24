import imaplib
import email
import random
import traceback
from email.header import decode_header
import os
import re
from datetime import datetime, timedelta
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import List, Dict, Optional, Union
import chardet
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import time
import ssl

import settings
from crud import (add_letter, add_attachment, list_vendors, add_vendor,
                  get_vendor_name_by_id, get_email_filter_by_vendor,
                  update_letter, delete_attachments_by_letter, list_configs_for_vendor_id, list_letters_email_ids)
from models import Letter, Attachment, Filters
from utils.imap import decode_folder_name
from utils.paths import pm


class ThreadSafeIMAPConnection:
    """Потокобезопасная обертка для IMAP соединения"""

    def __init__(self, email: str, password: str, imap_server: str = "imap.yandex.ru", port: int = 993):
        self.email = email
        self.password = password
        self.imap_server = imap_server
        self.port = port
        self._lock = threading.RLock()
        self._connection = None
        self.connected = False
        self.last_activity = time.time()

    def __enter__(self):
        """Контекстный менеджер - вход"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер - выход"""
        pass

    def connect(self):
        """Подключение к IMAP серверу"""
        with self._lock:
            if self.connected:
                return True

            try:
                print(f"🔄 Устанавливаем соединение с {self.imap_server}...")
                # Создаем SSL контекст без проверки сертификата
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

                self._connection = imaplib.IMAP4_SSL(
                    self.imap_server,
                    self.port,
                    ssl_context=ssl_context
                )
                self._connection.login(self.email, self.password)
                self.connected = True
                self.last_activity = time.time()
                print(f"✅ Успешное подключение к {self.email}")
                return True
            except Exception as e:
                print(f"❌ Ошибка подключения: {e}")
                self.connected = False
                self._connection = None
                return False

    def disconnect(self):
        """Отключение от сервера"""
        with self._lock:
            if self._connection and self.connected:
                try:
                    self._connection.logout()
                except:
                    pass
                self.connected = False
                self._connection = None

    def execute(self, command, *args):
        """Выполнение команды с блокировкой"""
        with self._lock:
            if not self.connected:
                raise Exception("Соединение не установлено")

            try:
                self.last_activity = time.time()
                result = getattr(self._connection, command)(*args)
                self.last_activity = time.time()
                return result
            except (imaplib.IMAP4.abort, ssl.SSLError, ConnectionError) as e:
                print(f"🔌 Потеряно соединение, переподключаемся... Ошибка: {e}")
                self.connected = False
                self._connection = None
                # Пытаемся переподключиться
                if self.connect():
                    # ВАЖНО: после переподключения нужно заново выбрать папку
                    # Но мы не знаем какая папка была выбрана, поэтому эта ответственность на вызывающей стороне
                    # Просто повторяем команду
                    try:
                        result = getattr(self._connection, command)(*args)
                        self.last_activity = time.time()
                        return result
                    except Exception as retry_e:
                        raise Exception(f"Не удалось выполнить команду после переподключения: {retry_e}")
                else:
                    raise Exception(f"Не удалось переподключиться: {e}")

    def is_connection_stale(self, timeout=300):
        """Проверяет, не устарело ли соединение"""
        return time.time() - self.last_activity > timeout


class ConnectionPool:
    """Пул IMAP соединений для многопоточного доступа"""

    def __init__(self, email: str, password: str, imap_server: str, port: int, max_connections: int = 5):
        self.email = email
        self.password = password
        self.imap_server = imap_server
        self.port = port
        self.max_connections = max_connections
        self._connections = queue.Queue()
        self._lock = threading.Lock()
        self._created_connections = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_all()

    def get_connection(self):
        """Получение соединения из пула"""
        try:
            # Пытаемся получить существующее соединение
            conn = self._connections.get_nowait()
            # Проверяем, что соединение активно и не устарело
            if conn.connected and not conn.is_connection_stale():
                return conn
            else:
                # Переподключаем если соединение разорвано или устарело
                print("🔌 Соединение устарело или разорвано, переподключаем...")
                conn.disconnect()
                if conn.connect():
                    return conn
                else:
                    # Если не удалось переподключиться, создаем новое
                    return self._create_new_connection()
        except queue.Empty:
            # Создаем новое соединение если достигли лимита
            return self._create_new_connection()

    def _create_new_connection(self):
        """Создание нового соединения"""
        with self._lock:
            if self._created_connections < self.max_connections:
                conn = ThreadSafeIMAPConnection(
                    self.email, self.password, self.imap_server, self.port
                )
                if conn.connect():
                    self._created_connections += 1
                    print(f"📡 Создано новое соединение ({self._created_connections}/{self.max_connections})")
                    return conn
            # Ждем доступное соединение
            print("⏳ Ожидание доступного соединения...")
            return self._connections.get()

    def return_connection(self, conn):
        """Возврат соединения в пул"""
        if conn.connected:
            # Проверяем, не устарело ли соединение перед возвратом в пул
            if conn.is_connection_stale():
                print("🔌 Соединение устарело, закрываем...")
                conn.disconnect()
            else:
                self._connections.put(conn)

    def close_all(self):
        """Закрытие всех соединений"""
        print("🔒 Закрытие всех соединений...")
        while not self._connections.empty():
            try:
                conn = self._connections.get_nowait()
                conn.disconnect()
            except queue.Empty:
                break
        self._created_connections = 0


class ProgressTracker:
    """Трекер общего прогресса"""

    def __init__(self):
        self.lock = threading.Lock()
        self.total_emails = 0
        self.processed_emails = 0
        self.successful_emails = 0
        self.failed_emails = 0
        self.start_time = time.time()

    def set_total(self, total: int):
        """Установка общего количества писем"""
        with self.lock:
            self.total_emails = total
            print(f"📊 Всего писем для обработки: {total}")

    def increment_processed(self, success: bool = True):
        """Увеличение счетчика обработанных писем"""
        with self.lock:
            self.processed_emails += 1
            if success:
                self.successful_emails += 1
            else:
                self.failed_emails += 1

            # Выводим прогресс каждые 10% или каждые 10 писем
            if self.total_emails > 0 and (self.processed_emails % 10 == 0 or
                                          self.processed_emails == self.total_emails):
                progress = (self.processed_emails / self.total_emails) * 100
                elapsed = time.time() - self.start_time
                if self.processed_emails > 0:
                    emails_per_second = self.processed_emails / elapsed
                    eta = (
                                      self.total_emails - self.processed_emails) / emails_per_second if emails_per_second > 0 else 0
                else:
                    emails_per_second = 0
                    eta = 0

                print(f"📈 Прогресс: {self.processed_emails}/{self.total_emails} "
                      f"({progress:.1f}%) | Успешно: {self.successful_emails} | "
                      f"Ошибки: {self.failed_emails} | Скорость: {emails_per_second:.1f} писем/сек | "
                      f"Осталось: {timedelta(seconds=int(eta))}")

    def get_summary(self):
        """Получение итоговой статистики"""
        elapsed = time.time() - self.start_time
        return {
            'total': self.total_emails,
            'processed': self.processed_emails,
            'successful': self.successful_emails,
            'failed': self.failed_emails,
            'elapsed_seconds': elapsed,
            'emails_per_second': self.processed_emails / elapsed if elapsed > 0 else 0
        }


class EmailProcessor:
    """Обработчик одного письма"""

    def __init__(self, connection_pool: ConnectionPool, email_uid: str, folder: str,
                 db_scope: List[Filters], vendors: List, progress_tracker: ProgressTracker):
        self.connection_pool = connection_pool
        self.email_uid = email_uid
        self.folder = folder
        self.db_scope = db_scope
        self.vendors = vendors
        self.progress_tracker = progress_tracker

    def process(self) -> Optional[Dict]:
        """Основная логика обработки письма"""
        try:
            # Получаем соединение из пула
            conn = self.connection_pool.get_connection()
            try:
                # Сначала получаем только заголовки для фильтрации
                email_headers = self.get_email_headers(conn, self.email_uid)
                if not email_headers:
                    print(f"❌ Не удалось получить заголовки для письма {self.email_uid}")
                    self.progress_tracker.increment_processed(False)
                    return None

                # Проверяем фильтры на основе заголовков
                if not self._passes_header_filters(email_headers):
                    #print(f"⏭️ Письмо {self.email_uid} не прошло фильтрацию по заголовкам")
                    self.progress_tracker.increment_processed(False)
                    return None

                # Если прошло фильтрацию - получаем полное содержимое
                print(f"✅ Письмо {self.email_uid} прошло фильтрацию, получаем содержимое...")
                email_info = self.get_full_email_content(conn, self.email_uid, email_headers)
                if email_info and email_info.get('excel_attachments'):
                    result = self.process_email_content(email_info)
                    self.progress_tracker.increment_processed(result is not None)
                    return result
                else:
                    print(f"ℹ️ В письме {self.email_uid} нет Excel вложений")
                    self.progress_tracker.increment_processed(False)
                    return None

            finally:
                # Всегда возвращаем соединение в пул
                self.connection_pool.return_connection(conn)

        except Exception as e:
            print(f"❌ Ошибка обработки письма {self.email_uid}: {e}")
            self.progress_tracker.increment_processed(False)

        return None

    def get_email_headers(self, conn: ThreadSafeIMAPConnection, email_uid: str) -> Optional[Dict]:
        """Получение только заголовков письма для быстрой фильтрации"""
        try:
            # Выбираем папку для этого соединения
            conn.execute('select', self.folder)

            # Получаем только заголовки
            status, msg_data = conn.execute('uid', 'FETCH', email_uid, "(BODY.PEEK[HEADER])")
            if status != "OK":
                return None

            email_headers = msg_data[0][1]
            msg = email.message_from_bytes(email_headers)

            subject = self._decode_header(msg["Subject"])
            from_ = self._decode_header(msg["From"])
            date = msg["Date"]
            try:
                vid = random.choice([vendor.id for vendor in self.vendors])
                d = parsedate_to_datetime(date)
                raw_from = from_.strip()
                match = re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', raw_from)
                sender_email = match.group(0) if match else from_
                letter = Letter(
                    letter_id=int(email_uid),
                    sender=sender_email,
                    subject=subject,
                    date=d,
                    vendor_id=vid
                )
                add_letter(letter)
            except Exception as e:
                print(f"❌ Ошибка при обработке письма {email_uid}: {e}")
            return {
                'uid': email_uid,
                'subject': subject,
                'from': from_,
                'date': date,
                'folder': self.folder
            }

        except Exception as e:
            print(f"❌ Ошибка получения заголовков письма {email_uid}: {e}")
            return None

    def _passes_header_filters(self, email_headers: Dict) -> bool:
        """Проверка письма по фильтрам на основе заголовков"""
        raw_from = email_headers['from'].strip()
        match = re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', raw_from)
        sender_email = match.group(0) if match else email_headers['from']

        # Ищем подходящего вендора и правило
        for rule in self.db_scope:
            # Проверяем активность вендора
            vendor = next((v for v in self.vendors if v.id == rule.vendor_id and v.active), None)
            if not vendor:
                continue

            # Проверяем отправителя
            rule_senders = [s.strip() for s in rule.senders.split(';')]
            if sender_email in rule_senders:
                # Проверяем тему письма
                if not self._check_email_subject(email_headers['subject'], rule):
                    return False

                return True

        return False

    def get_full_email_content(self, conn: ThreadSafeIMAPConnection, email_uid: str, headers: Dict) -> Dict:
        """Получение полного содержимого письма после прохождения фильтрации"""
        try:
            # ВАЖНО: Выбираем папку ПЕРЕД каждым запросом, так как соединение могло быть переподключено
            conn.execute('select', self.folder)
            # Получаем полное содержимое письма
            status, msg_data = conn.execute('uid', 'FETCH', email_uid, "(BODY.PEEK[])")
            if status != "OK":
                return {}

            email_body = msg_data[0][1]
            msg = email.message_from_bytes(email_body)

            email_info = {
                'uid': headers['uid'],
                'subject': headers['subject'],
                'from': headers['from'],
                'date': headers['date'],
                'attachments': [],
                'excel_attachments': [],
                'body': '',
                'body_html': '',
                'folder': headers['folder']
            }

            email_info.update(self._process_email_content(msg))
            return email_info

        except Exception as e:
            print(f"❌ Ошибка получения полного содержимого письма {email_uid}: {e}")
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

                if content_type == "text/plain" and "attachment" not in content_disposition:
                    body = self._decode_payload(part) or body
                elif content_type == "text/html" and "attachment" not in content_disposition:
                    body_html = self._decode_payload(part) or body_html
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

                            if self._is_excel_file(filename):
                                excel_attachments.append(attachment_info)
        else:
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

            encoding = part.get_content_charset()
            if not encoding:
                detected = chardet.detect(payload)
                encoding = detected.get('encoding', 'utf-8')

            encodings_to_try = [encoding, 'utf-8', 'cp1251', 'koi8-r', 'iso-8859-1', 'windows-1251']

            for enc in encodings_to_try:
                try:
                    if enc:
                        return payload.decode(enc, errors='replace')
                except (UnicodeDecodeError, LookupError):
                    continue

            return payload.decode('utf-8', errors='replace')

        except Exception as e:
            print(f"❌ Ошибка декодирования payload: {e}")
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
                        for enc in ['utf-8', 'cp1251', 'iso-8859-1']:
                            try:
                                decoded_header += part.decode(enc, errors='replace')
                                break
                            except UnicodeDecodeError:
                                continue
                else:
                    decoded_header += part

            return decoded_header
        except Exception as e:
            print(f"❌ Ошибка декодирования заголовка: {e}")
            return str(header) if header else ""

    def process_email_content(self, email_info: Dict) -> Optional[Dict]:
        """Обработка email и скачивание вложений"""
        raw_from = email_info['from'].strip()
        match = re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', raw_from)
        sender_email = match.group(0) if match else email_info['from']

        vendor_id, email_rule = self._find_vendor_and_rule(sender_email)
        if not vendor_id:
            return None

        downloaded_files = self.download_excel_attachments(email_info, vendor_id, email_rule)
        if downloaded_files:
            self._save_letter_and_attachments(email_info, sender_email, vendor_id, downloaded_files)

            return {
                'uid': email_info['uid'],
                'subject': email_info['subject'],
                'from': email_info['from'],
                'date': email_info['date'],
                'downloaded_files': downloaded_files,
                'excel_count': len(email_info['excel_attachments']),
            }

        return None

    def _find_vendor_and_rule(self, sender_email: str) -> tuple[Optional[int], Optional[Filters]]:
        """Поиск поставщика и правила для отправителя"""
        for rule in self.db_scope:
            # Проверяем активность вендора
            vendor = next((v for v in self.vendors if v.id == rule.vendor_id and v.active), None)
            if not vendor:
                continue

            if sender_email in [s.strip() for s in rule.senders.split(';')]:
                vendor_id = self._get_or_create_vendor(vendor.name)
                return vendor_id, rule

        return None, None

    def _get_or_create_vendor(self, vendor_name: str) -> int:
        """Получить ID поставщика или создать нового"""
        existing_vendor = next((v for v in self.vendors if v.name == vendor_name), None)
        if existing_vendor:
            return existing_vendor.id
        return add_vendor(vendor_name).id

    def _check_email_subject(self, subject: str, email_rule: Filters) -> bool:
        """Проверка темы письма по правилам"""
        return self._check_filter_conditions(subject, email_rule.subject_contains,
                                             email_rule.subject_excludes)

    def _check_filter_conditions(self, text: str, contains: str = None,
                                 excludes: str = None) -> bool:
        """Проверка условий фильтра"""
        if contains:
            patterns = [r.strip().lower() for r in contains.split(";")]
            if not any(p in text.lower() for p in patterns):
                return False

        if excludes:
            patterns = [r.strip().lower() for r in excludes.split(";")]
            if any(p in text.lower() for p in patterns):
                return False

        return True

    def download_excel_attachments(self, email_info: Dict, vendor_id: int,
                                   email_rule: Filters = None) -> List[str]:
        """Скачивание Excel вложений"""
        download_folder = os.path.join("attachments", str(vendor_id))
        downloaded_files = []
        excel_attachments = email_info.get('excel_attachments', [])

        for attachment in excel_attachments:
            try:
                filename = attachment['filename']
                payload = attachment['payload']

                if not filename or not payload:
                    continue

                clean_filename = re.sub(r'[<>:"/\\|?*]', '_', filename)

                if not self._check_attachment_approval(clean_filename, email_rule):
                    continue

                filepath = os.path.join(download_folder, clean_filename)
                abs_filepath = os.path.join(pm.get_user_data(), filepath)

                os.makedirs(os.path.dirname(abs_filepath), exist_ok=True)

                counter = 1
                original_filepath = abs_filepath
                while os.path.exists(abs_filepath):
                    name, ext = os.path.splitext(original_filepath)
                    abs_filepath = f"{name}_{counter}{ext}"
                    filepath = os.path.join(download_folder, f"{Path(original_filepath).stem}_{counter}{ext}")
                    counter += 1

                with open(abs_filepath, 'wb') as f:
                    f.write(payload)

                downloaded_files.append(filepath)

            except Exception as e:
                print(f"❌ Ошибка скачивания Excel файла {filename}: {e}")

        return downloaded_files

    def _check_attachment_approval(self, filename: str, email_rule: Filters) -> bool:
        """Проверка одобрения вложения по правилам"""
        if not email_rule:
            return True

        if not self._check_filter_conditions(filename, email_rule.filename_contains,
                                             email_rule.filename_excludes):
            return False

        if email_rule.extensions:
            extensions = [ext.strip() for ext in email_rule.extensions.split(",")]
            if not any(filename.lower().endswith(ext.lower()) for ext in extensions):
                return False

        return True

    def _save_letter_and_attachments(self, email_info: Dict, sender_email: str,
                                     vendor_id: int, downloaded_files: List[str]):
        """Сохранение письма и вложений в БД"""
        try:
            d = parsedate_to_datetime(email_info['date'])

            letter = Letter(
                letter_id=int(email_info['uid']),
                sender=sender_email,
                subject=email_info['subject'],
                date=d,
                vendor_id=vendor_id
            )

            try:
                add_letter(letter)
            except Exception:
                update_letter(letter)

            delete_attachments_by_letter(letter.letter_id)

            for file_path in downloaded_files:
                abs_path = Path(pm.get_user_data()) / file_path
                size = os.path.getsize(abs_path)

                attachment = Attachment(
                    letter_id=int(email_info['uid']),
                    file_name=os.path.basename(file_path),
                    file_path=file_path,
                    size=size
                )
                add_attachment(attachment)

        except Exception as e:
            print(f"❌ Ошибка сохранения в БД для письма {email_info['uid']}: {e}")


class FolderScanner:
    """Сканер папки для обработки писем"""

    def __init__(self, connection_pool: ConnectionPool, folder_name: str, db_scope: List[Filters],
                 vendors: List, criteria: str = "ALL", progress_tracker: ProgressTracker = None, emails_to_pass: list = []):
        self.connection_pool = connection_pool
        self.folder_name = folder_name
        self.db_scope = db_scope
        self.vendors = vendors
        self.criteria = criteria
        self.progress_tracker = progress_tracker
        self.emails_to_pass = emails_to_pass

    def scan_folder(self) -> List[Dict]:
        """Сканирование папки и обработка писем"""
        print(f"📁 Начинаем сканирование папки: {decode_folder_name(self.folder_name)}")

        try:
            # Получаем UID писем в папке
            email_uids = self.get_email_uids()
            if not email_uids:
                print(f"ℹ️ В папке {decode_folder_name(self.folder_name)} нет писем для обработки")
                return []

            print(f"🔍 Найдено {len(email_uids)} писем в папке {decode_folder_name(self.folder_name)}")

            # Обрабатываем письма в пуле потоков
            results = []
            with ThreadPoolExecutor(max_workers=5) as executor:
                # Запускаем обработку каждого письма
                future_to_email = {}
                for email_uid in email_uids:
                    processor = EmailProcessor(
                        self.connection_pool, email_uid, self.folder_name,
                        self.db_scope, self.vendors, self.progress_tracker
                    )
                    future = executor.submit(processor.process)
                    future_to_email[future] = email_uid

                # Собираем результаты
                for future in as_completed(future_to_email):
                    try:
                        result = future.result()
                        if result:
                            results.append(result)
                    except Exception as e:
                        email_uid = future_to_email[future]
                        print(f"❌ Ошибка обработки письма {email_uid}: {e}")

            return results

        except Exception as e:
            print(f"❌ Ошибка сканирования папки {decode_folder_name(self.folder_name)}: {e}")
            traceback.print_exc()
            return []

    def get_email_uids(self) -> List[str]:
        """Получение UID писем в папке"""
        try:
            conn = self.connection_pool.get_connection()
            try:
                conn.execute('select', self.folder_name)
                status, messages = conn.execute('uid', 'SEARCH', None, self.criteria)
                if status == "OK" and messages and messages[0]:
                    res = []
                    for msg in messages[0].split():
                        if isinstance(msg, bytes):
                            m = msg.decode()
                        else:
                            m = str(msg)
                        if int(m) not in self.emails_to_pass:
                            res.append(m)
                    return res
                else:
                    return []
            finally:
                self.connection_pool.return_connection(conn)
        except Exception as e:
            print(f"❌ Ошибка поиска писем в папке {self.folder_name}: {e}")
        return []


class OptimizedYandexIMAPClient:
    """Оптимизированная многопоточная версия IMAP клиента"""

    def __init__(self, email: str, password: str, imap_server: str = "imap.yandex.ru", port: int = 993):
        self.email = email
        self.password = password
        self.imap_server = imap_server
        self.port = port
        self.exluded_folders = [
            "Outbox", "Spam", "Trash", "\"Drafts|template\"",
            "Drafts", "Archive", "Sent"
        ]
        self.connection_pool = None
        self.vendors = list_vendors()
        self.progress_tracker = ProgressTracker()
        self.emails_to_pass = []

    def set_credentials(self, email: str, password: str, server: str = "imap.yandex.ru", port: int = 993):
        self.email = email
        self.password = password
        self.imap_server = server
        self.port = port

    def set_folders_to_exclude(self, folders: List[str]):
        self.exluded_folders = folders

    def set_emails_to_pass(self):
        vendor_list = []
        for vendor in self.vendors:
            not_this = False
            email_filter = get_email_filter_by_vendor(vendor.id)
            try:
                with open(Path(pm.get_user_data() / f"v{email_filter.id}"), 'r') as f:
                    dt = datetime.fromisoformat(f.read())
            except:
                dt = vendor.last_load - timedelta(days=10)
                with open(Path(pm.get_user_data() / f"v{email_filter.id}"), 'w') as f:
                    f.write(dt.isoformat())
            if dt >= vendor.last_load:
                not_this = True
            configs = list_configs_for_vendor_id(vendor_id=vendor.id)
            for config in configs:
                try:
                    with open(Path(pm.get_user_data() / str(config.id)), 'r') as f:
                        dt = datetime.fromisoformat(f.read())
                except:
                    dt = vendor.last_load - timedelta(days=10)
                    with open(Path(pm.get_user_data() / str(config.id)), 'w') as f:
                        f.write(dt.isoformat())
                if dt >= vendor.last_load:
                    continue
            if not not_this:
                vendor_list.append(vendor.id)
        self.emails_to_pass = list_letters_email_ids(vendor_list)

    def get_all_prices(self, limit_by_folder=None, days=None, since_date=None,
                       before_date=None, folder="attachments", unread_only=False,
                       simple_scope: Filters = None, max_folder_workers: int = 10):
        """Многопоточное получение всех прайсов"""
        self.progress_tracker = ProgressTracker()
        print("🚀 Запуск многопоточного сканирования писем...")

        # Настройка области поиска
        db_scope = self._setup_scope(simple_scope)
        if not db_scope:
            print("❌ Нет активных правил фильтрации для сканирования")
            return []

        print(f"📋 Активные правила фильтрации: {len(db_scope)}")

        # Создаем пул соединений
        self.connection_pool = ConnectionPool(
            self.email, self.password, self.imap_server, self.port,
            max_connections=max_folder_workers * 2
        )
        self.set_emails_to_pass()
        try:
            # Получаем список папок
            folders = self.get_available_folders()
            if not folders:
                print("❌ Не найдено папок для сканирования")
                return []

            print(f"📂 Найдено {len(folders)} папок для сканирования")

            # ИЗМЕНЕНИЕ ЗДЕСЬ: Определяем критерии поиска в зависимости от стратегии
            if limit_by_folder:
                # Для стратегии limit берем только последний месяц
                search_criteria = self._build_search_criteria(
                    days=30,  # Берем последние 30 дней вместо всех писем
                    since_date=None,
                    before_date=None,
                    unread_only=unread_only
                )
                print(f"🔍 Стратегия LIMIT: сканируем только последние 30 дней")
            else:
                # Обычная стратегия - используем переданные параметры
                search_criteria = self._build_search_criteria(
                    days=days,
                    since_date=since_date,
                    before_date=before_date,
                    unread_only=unread_only
                )

            # Сначала собираем все UID писем для подсчета общего количества
            print("🔍 Подсчет общего количества писем...")
            all_email_uids = []
            for folder_name in folders:
                scanner = FolderScanner(self.connection_pool, folder_name, db_scope, self.vendors, search_criteria, emails_to_pass=self.emails_to_pass)
                folder_uids = scanner.get_email_uids()
                all_email_uids.extend(folder_uids)
                print(f"   {decode_folder_name(folder_name)}: {len(folder_uids)} писем")

            total_emails = len(all_email_uids)
            self.progress_tracker.set_total(total_emails)

            if total_emails == 0:
                print("ℹ️ Нет писем для обработки")
                return []

            # Сканируем папки в пуле потоков
            all_results = []
            with ThreadPoolExecutor(max_workers=max_folder_workers) as executor:
                # Запускаем сканирование каждой папки
                future_to_folder = {}
                for folder_name in folders:
                    scanner = FolderScanner(
                        self.connection_pool, folder_name, db_scope, self.vendors, search_criteria,
                        self.progress_tracker, emails_to_pass=self.emails_to_pass
                    )
                    future = executor.submit(scanner.scan_folder)
                    future_to_folder[future] = folder_name

                # Собираем результаты
                completed = 0
                for future in as_completed(future_to_folder):
                    folder_name = future_to_folder[future]
                    completed += 1
                    try:
                        folder_results = future.result()
                        all_results.extend(folder_results)
                        print(
                            f"✅ [{completed}/{len(folders)}] Завершено сканирование папки {decode_folder_name(folder_name)}: найдено {len(folder_results)} писем")
                    except Exception as e:
                        folder_name = future_to_folder[future]
                        print(f"❌ [{completed}/{len(folders)}] Ошибка сканирования папки {decode_folder_name(folder_name)}: {e}")

            # Выводим итоговую статистику
            summary = self.progress_tracker.get_summary()
            print(f"\n🎉 СКАНИРОВАНИЕ ЗАВЕРШЕНО!")
            print(f"📊 ИТОГИ:")
            print(f"   Всего писем: {summary['total']}")
            print(f"   Обработано: {summary['processed']}")
            print(f"   Успешно: {summary['successful']}")
            print(f"   Ошибки: {summary['failed']}")
            print(f"   Затрачено времени: {timedelta(seconds=int(summary['elapsed_seconds']))}")
            print(f"   Скорость: {summary['emails_per_second']:.1f} писем/сек")
            print(f"   Найдено писем с Excel: {len(all_results)}")

            return self._format_results(all_results)

        except Exception as e:
            print(f"💥 Критическая ошибка при обработке писем: {e}")
            traceback.print_exc()
            return []
        finally:
            if self.connection_pool:
                self.connection_pool.close_all()

    def get_available_folders(self) -> List[str]:
        """Получение списка доступных папок"""
        try:
            conn = self.connection_pool.get_connection()
            try:
                status, folders = conn.execute('list')
                if status == "OK":
                    available_folders = []
                    for folder_line in folders:
                        folder_str = folder_line.decode() if isinstance(folder_line, bytes) else str(folder_line)
                        parts = folder_str.split('"|"')
                        if len(parts) > 1:
                            folder_name = parts[-1].strip()
                            if folder_name not in self.exluded_folders:
                                decoded_name = decode_folder_name(folder_name)
                                available_folders.append(folder_name)
                    return available_folders
                else:
                    return []
            finally:
                self.connection_pool.return_connection(conn)
        except Exception as e:
            print(f"❌ Ошибка получения списка папок: {e}")
        return []

    def _setup_scope(self, simple_scope: Filters = None) -> List[Filters]:
        """Настройка области поиска"""
        if simple_scope:
            return [simple_scope]
        else:
            db_scope = []
            for vendor in self.vendors:
                if vendor.active:
                    rule = get_email_filter_by_vendor(vendor.id)
                    if rule:
                        db_scope.append(rule)
            return db_scope

    def _build_search_criteria(self, days: int, since_date: datetime, before_date: datetime,
                               unread_only: bool) -> str:
        """Построение критериев поиска (только по дате и статусу)"""
        criteria_parts = []

        # Критерии по дате
        date_criteria = self._build_date_criteria(days, since_date, before_date)
        if date_criteria:
            criteria_parts.append(date_criteria)

        # Только непрочитанные
        if unread_only:
            criteria_parts.append('UNSEEN')

        return f'({" ".join(criteria_parts)})' if criteria_parts else "ALL"

    def _build_date_criteria(self, days: int = None, since_date: datetime = None,
                             before_date: datetime = None) -> str:
        """Построение критериев поиска по дате"""
        if days:
            since_date = datetime.now() - timedelta(days=days)

        if since_date:
            since_date = since_date - timedelta(days=1)
            since_str = since_date.strftime("%d-%b-%Y").lstrip('0')

        if before_date:
            before_date = before_date + timedelta(days=1)
            before_str = before_date.strftime("%d-%b-%Y").lstrip('0')

        if days or (since_date and before_date):
            return f'SINCE {since_str}' + (f' BEFORE {before_str}' if before_date else '')
        elif since_date:
            return f'SINCE {since_str}'
        elif before_date:
            return f'BEFORE {before_str}'

        return ""

    def _format_results(self, results: List[Dict]) -> List[Dict]:
        """Форматирование результатов"""
        out = []

        if results:
            for info in results:
                for file_path in info['downloaded_files']:
                    out.append({
                        "subject": info['subject'],
                        "filename": file_path,
                        "date": info['date'],
                    })

        return out


# Создание клиента с настройками
s = settings.get_settings()
client = OptimizedYandexIMAPClient(
    s.get('email_username'),
    s.get('email_password'),
    s.get('email_server', 'imap.yandex.ru'),
    int(s.get('email_port', 993))
)

if __name__ == '__main__':
    results = client.get_all_prices(
        days=30,
        max_folder_workers=2
    )
    print(f"🎊 Обработка завершена! Результатов: {len(results)}")