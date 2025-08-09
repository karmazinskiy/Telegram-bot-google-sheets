# в этом коде фото отделены от шаблонов
# данные отправляются в гугл таблицу по айди таблицы в разные листы таблицы по ID листа
import os
from dotenv import load_dotenv
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import logging
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from google.oauth2.service_account import Credentials

from datetime import datetime
from collections import OrderedDict #отвечает за порядок элементов в словаре, чтоб дату фактическую в отчетах ставить первой


#ПЕРЕМЕННЫЕ
# Загружаем переменные из .env
load_dotenv()
# Получаем JSON строку из переменной окружения
service_account_json_str = os.getenv("SERVICE_ACCOUNT")


# Читаем переменные
TOKEN = os.getenv("TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))  # Приводим к int
your_gmail = os.getenv("YOUR_GMAIL")
service_account = json.loads(service_account_json_str) # Преобразуем строку в объект JSON
spreadsheet_id = os.getenv("SPREADSHEET_ID")

# Словарь predefined_sheet_ids
predefined_sheet_ids = {
    "report_ostatki": os.getenv("REPORT_OSTATKI"),
    "report_igry": os.getenv("REPORT_IGRY"),
    "report_posetiteli": os.getenv("REPORT_POSETITELI"),
}


# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Шаблоны отчетов
templates = {
    'report_ostatki': re.compile(
        r"^.*\bОстатки\b.*\s*\n(?:\s*\n)*"  # Заголовок "Остатки" в первой строке, допускаются любые пробелы и символы
        r"Дата\s*отчета\s*(?:\(\s*в\s*формате\s*дд\.мм\s*\))?:\s*\d{2}\.\d{2}\s*(?:\n\s*)*"
        r"ФИ\s*админа.*?:\s*\S.*\n"# ФИ администратора (обязательно непустое значение)
        r"Печенье.*?:\s*\d+\s*\n"# Печенье (обязательное число)
        r"Соты.*?:\s*\d+\s*\n"# Соты (обязательное число)
        r"Банкноты.*?:\s*\d+\s*\n"# Банкноты (обязательное число)
        r"Призы.*?:\s*\d+\s*\n"# Призы (обязательное число)
        r"Угощение.*?:\s*\d+\s*\n"# Угощение (обязательное число)
        r"Поломки.*?:\s*\S.*\n"# поломки (обязательно непустое значение)
        r"Плитки\s*нерабочие.*?:\s*\d+\s*\n"# Плитки нерабочие (обязательное число)
        r"Футболок\s*общее\s*число.*?:\s*\d+\s*\n"# Футболок общее число (обязательное число)
        r"Футболок\s*грязных.*?:\s*\d+\s*\n"# Футболок грязных (обязательное число)
        r"Костюмов\s*грязных.*?:\s*\d+\s*\n"# Костюмов грязных (обязательное число)
        r"Вода.*?:\s*\S.*\n"# Вода (обязательно непустое значение)
        r"Стаканы.*?:\s*\S.*\n"# Стаканы (обязательно непустое значение)
        r"Салфетки.*?:\s*\S.*\n"# Салфетки (обязательно непустое значение)
        r"Чай.*?:\s*\S.*\n"# Чай (обязательно непустое значение)
        r"Cахар.*?:\s*\S.*\n"# Сахар (обязательно непустое значение)
        r"(Примечания.*?:\s*.*\n)?",# Примечания 
        re.MULTILINE | re.IGNORECASE
    ),

    'report_igry': re.compile(
        r"^.*\bИгры\b.*\n(?:\s*\n)*"  # Первая строка должна содержать слово "Игры", допускаются пустые строки после нее
        r"ФИ\s*админа:\s*\S.*\n(?:\s*\n)*"  # Обязательно должно быть значение после двоеточия
        r"Дата\s*игры\s*(?:\(\s*в\s*формате\s*дд\.мм\s*\))?:\s*\d{2}\.\d{2}\s*(?:\n\s*)*" # Обязательная дата в формате дд.мм
        r"Время\s*игры\s*(?:\(\s*в\s*формате\s*чч\:мм\s*\))?:\s*\d{2}:\d{2}\s*(?:\n\s*)*"# Обязательно должно быть значение после двоеточия
        r"Тариф:\s*\S.*\n(?:\s*\n)*" # Обязательно должно быть значение после двоеточия
        r"Количество\s*участников.*?:\s*\d+\s*\n"# Обязательное числовое значение после двоеточия
        r"Сумма.*?:\s*\d+(?:[,]\d+)?\s*\n(?:\s*\n)*" # Обязательно числовое значение после двоеточия, допускаются запятые
        r"Способ\s*оплаты\s*\(наличные/перевод\):\s*\S.*\n(?:\s*\n)*" # Обязательно должно быть значение после двоеточия
        r"Доп\.программа.*?:\s*\d+\s*\n" # Обязательное числовое значение после двоеточия
        r"Отзывы:\s*\S.*\n(?:\s*\n)*" # Обязательно должно быть значение после двоеточия
        r"Что\s*пошло\s*не\s*так:\s*.*\n?", # После двоеточия любое содержимое
        re.MULTILINE | re.IGNORECASE  # Поддержка многострочности и игнорирования регистра

    ),

    'report_posetiteli': re.compile(
        r"^.*\bПосетители\b.*\n(?:\s*\n)*"  # Первая строка: только слово "Посетители" с любыми пробелами
        r"Дата\s*отчета\s*(?:\(\s*в\s*формате\s*дд\.мм\s*\))?:\s*\d{2}\.\d{2}\s*(?:\n\s*)*"  # обязательная Дата в формате дд.мм  
        r"ФИ\s*админа.*?:\s*\S.*\n"  # ФИ администратора (обязательно непустое значение)
        r"Посетители:\s*\S.*\s*\n?$",  # Обязательное содержание после двоеточия в последней строке
        re.MULTILINE | re.IGNORECASE  # Поддержка многострочности и игнорирования регистра
    ),
    
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет меню с кнопками выбора шаблона."""
    keyboard = [
        [InlineKeyboardButton("Остатки", callback_data='report_ostatki')],
        [InlineKeyboardButton("Игры", callback_data='report_igry')],
        [InlineKeyboardButton("Посетители", callback_data='report_posetiteli')],
        [InlineKeyboardButton("Инструкции к заполнению отчетов", callback_data='Instructions')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите шаблон отчета:", reply_markup=reply_markup)


async def report_template(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет пользователю текст шаблона по выбранной кнопке."""
    query = update.callback_query
    await query.answer()

    template_text = {
        'report_ostatki': (
            "Отчет 'Остатки'\n"
            "Дата отчета (в формате дд.мм):\n"
            "ФИ админа:\n"
            "Печенье (число):\n"
            "Соты (число):\n"
            "Банкноты (число):\n"
            "Призы (число):\n"
            "Угощение (число):\n"
            "Поломки:\n"
            "Плитки нерабочие (число):\n"
            "Футболок общее число (число):\n"
            "Футболок грязных (число):\n"
            "Костюмов грязных (число):\n"
            "Вода (полная, 1/2, 1/3, нет):\n"
            "Стаканы (есть, мало, нет):\n"
            "Салфетки (есть, мало, нет):\n"
            "Чай (есть, мало, нет):\n"
            "Cахар (есть, мало, нет):\n"
            "Примечания:\n"

        ),
        'report_igry': (
            "Отчет 'Игры'\n"
            "ФИ админа:\n"
            "Дата игры (в формате дд.мм):\n"
            "Время игры (в формате чч:мм):\n"
            "Тариф:\n"
            "Количество участников (число):\n"
            "Сумма (число):\n"
            "Способ оплаты (наличные/перевод):\n"
            "Доп.программа (число):\n"
            "Отзывы:\n"
            "Что пошло не так:\n"          
        ),
        'report_posetiteli': (
            "Отчет 'Посетители'\n"
            "Дата отчета (в формате дд.мм):\n"
            "ФИ админа:\n"
            "Посетители:\n"
        ),
        "Instructions": (
        "Отправьте /start в чат бота.\nВыберите шаблон, нажав на соответствующую кнопку. "
        "Скопируйте шаблон и дополните его необходимыми данными. \nДанные вводите строго в формате, указанном в шаблоне. "
        "\nНе допускайте изменений в «шаблонной» части, избегайте пробелов и лишних символов после двоеточий в шаблонах. "
        "\nВсе поля обязательные, кроме поля «примечания» в отчете «Остатки». \nЕсли в полях, требующих описания, отсутствует "
        "необходимость что-либо указывать, напишите слово 'нет'. \nВсе дробные числа записывайте с \",\" (запятой), "
        "в вводимом тексте избегайте \":\" (двоеточий). \nФото и текст отчета отправляйте отдельно, не подписывайте фото при отправке."
        )
    }

    # Логика для кнопки "Игры"
    if query.data == 'report_igry':
        # Отправляем информационное сообщение
        await query.edit_message_text(
            "В данном отчете требуется 1-3 фото игроков. Сначала отправьте заполненный отчет 'Игры', затем отправьте фото. "
            "Не группируйте отчет и фото в одном сообщении."
        )
        # Отправляем шаблон отдельно
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=template_text.get(query.data, "Шаблон не найден.")
        )
    else:
        # Для остальных кнопок отправляем только шаблон
        await query.edit_message_text(template_text.get(query.data, "Шаблон не найден."))

def remove_parentheses(cleaned_text: str) -> str:
    """Удаляет все скобки и их содержимое из текста и обновляет переменную cleaned_text."""
    cleaned_text = re.sub(r"\s*\([^)]*\)", "", cleaned_text)  # Удаляем скобки и пробел перед ними
    return cleaned_text  # Возвращаем обновленный текст

def add_alerts_to_numbers(text: str) -> str:
    """Добавляет символы к числам в зависимости от их значения, кроме строки 'Дата отчета'."""
    
    def replace_func(match, category):
        try:
            value = int(match.group(2))
            
            # Отдельные правила для конкретных категорий
            if category == "Футболок грязных":
                if value >= 20:
                    return f"{value} ⚠️"
                else:
                    return str(value)
            elif category == "Костюмов грязных":
                if value >= 2:
                    return f"{value} ⚠️"
                else:
                    return str(value)

            # Общие правила для остальных категорий
            if value == 0:
                return str(value)
            if value < 25:
                return f"{value} ⚠️"
            elif value < 50:
                return f"{value} ⚡"
            return str(value)
        except ValueError:
            logger.error(f"Не удалось обработать число: {match.group(2)}")
            return match.group(2)

    categories = [
        "Печенье", "Соты", "Банкноты", "Призы", "Угощение",
        "Плитки нерабочие", "Футболок общее", "Футболок грязных", "Костюмов грязных"
    ]

    for category in categories:
        pattern = rf"({category}(?:\s*\([^)]*\))?:\s*)(\d+)"
        text = re.sub(pattern, lambda m: m.group(1) + replace_func(m, category), text)

    return text

# Функция для добавления данных в уже созданые  Google Таблицы по ID таблицы и ID листа таблицы _________________________________________________________    
def add_data_to_specific_sheets_by_id(matched_template: str, message_data: dict): #, sheet_id: str
    """
    Добавляет данные в указанный лист таблицы по его ID, на основе типа шаблона.
    Если таблица или лист не найдены, вызывает ошибку.

    :param matched_template: Тип шаблона, определяющий, в какую таблицу добавлять данные.
    :param message_data: Словарь с данными (ключи - названия столбцов, значения - данные).
    :param sheet_id: ID листа, в который нужно добавить данные.
    """
    print(f"Начинаем обработку шаблона: {matched_template}")

    if matched_template not in predefined_sheet_ids:
        print(f"Шаблон '{matched_template}' не найден в predefined_sheet_ids.")
        raise ValueError(f"Шаблон '{matched_template}' не поддерживается.")

    
    #spreadsheet_id = predefined_sheet_ids[matched_template]
    print(f"Получен spreadsheet_id: {spreadsheet_id}")
    sheet_id = predefined_sheet_ids[matched_template] 
    print(f"Получен sheet_id: {sheet_id}")
    # Указываем scope (области доступа) для работы с Google Sheets
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        # Настройка подключения к Google Sheets API
        
        print("Настройка подключения к Google Sheets API...")
        # scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]# вариант для подключения к сервисному аккаунты по пути к json файлу, расположенгому в директории
        # creds = ServiceAccountCredentials.from_json_keyfile_name(service_account, scope) # вариант для подключения к сервисному аккаунты по пути к json файлу, расположенгому в директории
        creds = Credentials.from_service_account_info(service_account, scopes=SCOPES)  # Передаем словарь и scope как параметр
        client = gspread.authorize(creds)
        print("Подключение установлено.")

        # Открываем таблицу по ID
        spreadsheet = client.open_by_key(spreadsheet_id)
        print("Таблица успешно открыта.")

        # Открываем лист по его ID
        try:
            worksheet = None
            for sheet in spreadsheet.worksheets():
                if sheet.id == int(sheet_id):
                    worksheet = sheet
                    break

            if worksheet is None:
                print(f"Лист с ID '{sheet_id}' не найден в таблице.")
                raise ValueError(f"Лист с ID '{sheet_id}' не существует в таблице.")

            print(f"Лист с ID '{sheet_id}' успешно открыт.")
        except Exception as e:
            print(f"Ошибка при попытке найти лист с ID '{sheet_id}': {e}")
            raise

        # Добавляем данные
        values = list(message_data.values())
        worksheet.append_row(values)
        print(f"Данные успешно добавлены в лист с ID '{sheet_id}': {values}")

    except gspread.SpreadsheetNotFound:
        print(f"Таблица с ID '{spreadsheet_id}' не найдена. Убедитесь, что таблица существует.")
    except Exception as e:
        print(f"Ошибка при работе с Google Sheets: {e}")

#функция для парсинга данных из сообщения_________________________________________________________________________
def parse_message_data(template: str, message: str) -> dict:
    """
    Парсит текст сообщения в словарь данных для Google Таблицы.
    :param template: Шаблон сообщения
    :param message: Текст сообщения
    :return: Словарь с данными
    """
    data = OrderedDict()

    # Добавляем "Фактическая дата отправки отчета"
    data["Фактическая дата отправки отчета"] = datetime.today().strftime("%d.%m.%Y")

    # Определяем нужные поля
    if template == 'report_ostatki':
        fields = ["Дата отчета", "ФИ админа", "Печенье", "Соты", "Банкноты", "Призы", "Угощение", "Поломки", "Плитки нерабочие", "Футболок общее", "Футболок грязных", "Костюмов грязных", "Вода", "Стаканы", "Салфетки", "Чай", "Cахар", "Примечания"]
    elif template == 'report_igry':
        fields = ["ФИ админа", "Дата игры", "Время игры", "Тариф", "Количество участников", "Сумма", "Способ оплаты", "Доп.программа", "Отзывы", "Что пошло не так"]
    elif template == 'report_posetiteli':
        fields = ["Дата отчета", "ФИ админа", "Посетители"]
    else:
        return data  # Если шаблон неизвестен, возвращаем только дату

    values = re.findall(r":\s*(?:мм:\s*)?([0-2]?\d:[0-5]\d|[\w\d\.,\-⚠️⚡/ ]+)(?=\n|$)", message)
    parsed_data = dict(zip(fields, values))  

    # Добавляем остальные данные в `OrderedDict`
    data.update(parsed_data)

    print(template)
    
    for key in data:
        value = data[key].strip()  # Убираем пробелы

        # Проверяем, является ли значение датой (формат ДД.ММ.ГГГГ)
        try:
            datetime.strptime(value, "%d.%m.%Y")  
            continue  # Если это дата, оставляем строкой
        except ValueError:
            pass  

        # Числа с точкой (например, 14.30) оставляем строкой
        if re.match(r"^\d+\.\d+$", value):  
            continue  

        # Числа с запятой (5000,50 → 5000.50)
        if re.match(r"^\d+,\d+$", value):  
            value = value.replace(',', '.')  
            data[key] = float(value)  
            continue  

        # Целые числа (5000 → 5000)
        if value.isdigit():  
            data[key] = int(value)  
            continue  

    print("выполнен парсинг данных:", data)
    return data

# Функция для обработки сообщений с фото
async def forward_message_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    try:
        # Если в сообщении есть фото
        if update.message.photo:
            if message.caption:  # Если к фото прикреплён текст
                await message.reply_text("Ваше сообщение и фото не отправлены. Пожалуйста, отправляйте фото без текста.\nСначала отправьте отчет, затем отдельно отправьте фото.")
            else:
                logger.info(f"Получено {len(update.message.photo)} фото.")
                # Пересылаем всё сообщение целиком (включая фото)
                await update.message.forward(chat_id=CHAT_ID)
                await update.message.reply_text(
                        "Ваш отчет принят.\n\nНапишите /start в чат, чтобы начать работу."
                    )
           
    except Exception as e:
        logger.error(f"Ошибка при пересылке сообщения: {e}")
        # Логируем для дальнейшей диагностики
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")
        await context.bot.send_message(chat_id=CHAT_ID, text=f"Произошла ошибка при пересылке сообщения: {e}")



async def forward_to_director(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Пересылает сообщения директору, если они соответствуют шаблону."""
    try:
        
        cleaned_text = (update.message.text or "") #+ (update.message.caption or "")

        # Логируем исходное сообщение
        logger.info(f"Получено сообщение от пользователя {update.message.from_user.id}: {cleaned_text}")

        # Если текст отсутствует, отправляем уведомление пользователю
        if not cleaned_text:
            await update.message.reply_text(
                "Сообщение должно содержать текст, соответствующий шаблону."
            )
            return

        # Удаляем пробелы между числами (например, в датах и времени)
        cleaned_text = re.sub(r'\s*(?<=\d)\s*(?=\d)', '', cleaned_text)
        
        # Логируем текст сообщения
        logger.info(f"Получен чистый текст сообщения: {cleaned_text}")
                
       # Проверяем соответствие шаблонам
        matched_template = None
        template_regex = None  # Инициализируем переменную шаблона перед использованием
        for template_key, template_regex_candidate in templates.items():
            logger.info(f"Попытка сопоставления с шаблоном {template_key}")
            if template_regex_candidate.match(cleaned_text):
                matched_template = template_key
                template_regex = template_regex_candidate  # Присваиваем шаблон
                break

        if not matched_template:
            logger.info("Сообщение не прошло валидацию.")
            await update.message.reply_text(
                "Ваше сообщение не соответствует шаблону. Проверьте:\n"
                "- Все обязательные поля заполнены\n"
                "- Дробные числа должны быть с запятой, например \"500,23\"\n"
                "- Нет лишних пробелов\n"
                "- Формат текста соответствует требованиям.\n\nНапишите /start в чат, чтобы начать работу."
            )
            return
       
        print(matched_template)
        
        if matched_template:
            print ("Вызываю вункцию удаления всего что в скобках")
            # Вызов функции для удаления всего что в скобках
            cleaned_text = remove_parentheses(cleaned_text)

            # Вызов функции для добавления символов к числам
            print ("Вызываю вункцию добавления символов")
            cleaned_text = add_alerts_to_numbers(cleaned_text)
            print(cleaned_text)

            # Пересылаем текст сообщения директору
            logger.info(f"Пересылка текста сообщения в чат директора: {CHAT_ID}")
                
            if cleaned_text:
                await context.bot.send_message(chat_id=CHAT_ID, text=cleaned_text)

            # Парсим данные из сообщения
            message_data = parse_message_data(matched_template, cleaned_text)
            
            # Создаем и заполняем Google Таблицу
            add_data_to_specific_sheets_by_id(matched_template, message_data)  # Отправка данных в таблицу


            if matched_template =="report_igry":
                await update.message.reply_text(
                    "Пожалуйста, пришлите 1-3 фото игроков" 
                )

            else:
                await update.message.reply_text(
                    "Ваш отчет принят.\n\nНапишите /start в чат, чтобы начать работу."
                )

       
    except Exception as e:
        logger.error(f"Ошибка при пересылке сообщения: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")

def main() -> None:
    """Запуск бота."""
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(report_template))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_to_director)) #forward_to_director
    app.add_handler(MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND,forward_message_foto)) #forward_to_director

    app.run_polling()


if __name__ == "__main__":
     main()
