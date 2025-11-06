import imaplib
import re


def decode_modified_utf7(encoded_str):
    """
    Декодирует строку в формате modified UTF-7, используемом в IMAP.
    """
    # Убираем начальный & и конечный -
    if encoded_str.startswith('&') and encoded_str.endswith('-'):
        encoded_str = encoded_str[1:-1]

    # Заменяем запятые на слеши (кодировка base64 использует +, но в modified UTF-7 это ,)
    encoded_str = encoded_str.replace(',', '/')

    # Добавляем padding если нужно
    padding = 4 - len(encoded_str) % 4
    if padding != 4:
        encoded_str += '=' * padding

    try:
        decoded_bytes = imaplib._utf7_decode(encoded_str)[0]
        return decoded_bytes.decode('utf-16-be')
    except:
        # Если стандартное декодирование не работает, попробуем base64
        try:
            import base64
            decoded_bytes = base64.b64decode(encoded_str + '===')
            return decoded_bytes.decode('utf-16-be')
        except:
            return encoded_str  # Возвращаем как есть если декодирование не удалось


def decode_folder_name(folder_str):
    """
    Декодирует всю строку с папкой, извлекая и декодируя закодированные части.
    """
    # Ищем все закодированные части (между & и -)
    encoded_parts = re.findall(r'&[A-Za-z0-9+/,]*?-', folder_str)

    decoded_str = folder_str
    for encoded_part in encoded_parts:
        decoded_part = decode_modified_utf7(encoded_part)
        decoded_str = decoded_str.replace(encoded_part, decoded_part)

    return decoded_str