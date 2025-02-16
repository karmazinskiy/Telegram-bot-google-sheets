from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Путь к вашему файлу ключа JSON
SERVICE_ACCOUNT_FILE = 'path/to/your/service_account.json'

# Список необходимых прав доступа
SCOPES = ["https://www.googleapis.com/auth/drive"]

# Аутентификация через сервисный аккаунт
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

# Создаем сервис для работы с Google Drive API
drive_service = build('drive', 'v3', credentials=creds)

# ID файла, который вы хотите удалить
file_id = 'ID_ТАБЛИЦЫ_КОТОРУЮ_ХОТИТЕ_УДАЛИТЬ'

try:
    # Удаляем файл
    drive_service.files().delete(fileId=file_id).execute()
    print(f"Таблица с ID {file_id} успешно удалена.")
except Exception as e:
    print(f"Ошибка при удалении файла: {e}")