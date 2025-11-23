from utils.imap import decode_folder_name
from ya_client import client

if __name__ == '__main__':
    client.connect()

    for folder_line in client.list_folders():
        mails = []
        parts = folder_line.split('"|"')
        if len(parts) > 1:
            folder_name = parts[-1].strip()
            if folder_name in client.exluded_folders:
                continue
            decoded_name = decode_folder_name(folder_name)
            print(f"Ищем в папке: {decoded_name}")
            # self.set_mark_as_read_on_download(False)
            client.select_folder(folder_name)
            client.senders = ["elfista@mail.ru"]
            ids = client.search_emails("SINCE 16-Nov-2025 BEFORE 20-Nov-2025")
            for r in ids:
                details = client.get_email_details(r)
                if details:
                    print(details['subject'] + ' ' + details['from'] + ' ' + details['date'])
    client.disconnect()