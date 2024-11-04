import requests
from bs4 import BeautifulSoup
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
from apscheduler.schedulers.background import BackgroundScheduler
import logging
import pytz
from database import Database

# Настawienie logowania
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Inicjalizacja bazy danych
db = Database()

scheduler = BackgroundScheduler()
timezone = pytz.timezone('Europe/Warsaw')

# Lista linków do parsowania
urls = {
    "Kantor Grand Olimp": "https://zlata.ws/pl/kantory/lublin/kantorgrandolimp/",
    "Kantor Korab": "https://zlata.ws/pl/kantory/lublin/kantorkorab/",
    "1913 Kantor": "https://zlata.ws/pl/kantory/lublin/1913/",
    "Kantor Tuus": "https://zlata.ws/pl/kantory/lublin/kantortuus/",
    "Kantor Anna Janek": "https://zlata.ws/pl/kantory/lublin/kantorannajanek/",
    "Kantor Paciorkowski": "https://zlata.ws/pl/kantory/lublin/paciorkowski/",
    "Kantor Witosa": "https://zlata.ws/pl/kantory/lublin/kantorzamkowy2/",
    "Kantor Probostwo": "https://zlata.ws/pl/kantory/lublin/kantorzamkowy1/",
    "Kantor Tarasy": "https://zlata.ws/pl/kantory/lublin/kantortarasylublin/",
    "Kantor Grazyna": "https://zlata.ws/pl/kantory/lublin/kantorygrazynalublin/",
    "Kantor Plaza": "https://zlata.ws/pl/kantory/lublin/kantorplazalublin/"
}

# Funkcja do parsowania danych ze strony
def parse_kantor_data(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    card = soup.find('div', class_='msg')
    if not card:
        logging.warning(f"No data found for URL: {url}")
        return None

    card_name = card.find('strong').text.strip()
    name = card.find_all('strong')[1].text.strip()
    address = card.find_all('strong')[2].text.strip()
    phone = card.find_all('strong')[3].text.strip()
    work = card.find_all('strong')[4].text.strip()
    update_time = card.find_all('strong')[5].text.strip()
    comment = card.find_all('strong')[6].text.strip()

    table = soup.find('table', class_='table')
    rows = table.find_all('tr')[1:]
    currencies_info = []
    for row in rows:
        cols = row.find_all('td')
        currency_name = cols[0].text.strip().split("\n")[0].strip()
        buy_price = cols[1].text.strip()
        sell_price = cols[2].text.strip()
        currencies_info.append(f"*{currency_name}*: {buy_price} / {sell_price}")

    # Aktualizacja danych w bazie danych
    for currency_info in currencies_info:
        currency_data = currency_info.split(': ')
        if len(currency_data) == 2:
            currency, prices = currency_data
            buy_price, sell_price = prices.split(' / ')
            db.update_exchange_rate(name, currency, buy_price, sell_price)

    currency_info_text = "\n".join(currencies_info)
    maps_link = f"https://www.google.com/maps/search/?api=1&query={address}"
    kantor_info = f"""
    *{card_name}*
    *🏦 Nazwa:* {name}
    *📍 Adres:* [{address}]({maps_link})
    *📞 Telefon:* {phone}
    *🕒 Godziny pracy:* {work}
    *🗓 Ostatnia aktualizacja:* {update_time}
    *💱 Kursy walut (Kupno/Sprzedaż):*
    {currency_info_text}
    *📋 Komentarz:* {comment if comment else 'Brak komentarza'}
    """.strip()

    return kantor_info

def update_all_kantors():
    for kantor_name, url in urls.items():
        try:
            kantor_info = parse_kantor_data(url)
        except Exception as e:
            logging.error(f"Błąd podczas przetwarzania kantoru {kantor_name}: {e}")

    
    # Запуск обновления данных каждые 30 минут
    scheduler.add_job(update_all_kantors, 'interval', minutes=30, timezone=timezone)
    scheduler.start()
# Запуск начального парсинга данных перед стартом бота
update_all_kantors()

# Funkcja do wyświetlania głównego menu
def show_main_menu(update: Update, context: CallbackContext) -> None:
    keyboard = [
        [KeyboardButton("Kantors")],
        [KeyboardButton("Najlepszy kurs")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    update.message.reply_text('Wybierz opcję z menu głównego:', reply_markup=reply_markup)

# Funkcja do wyświetlania listy kantorów
def show_kantors(update: Update, context: CallbackContext) -> None:
    keyboard = [[KeyboardButton(name)] for name in urls.keys()]
    keyboard.append([KeyboardButton("Wróć do menu głównego")])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    update.message.reply_text('Wybierz kantor:', reply_markup=reply_markup)

# Funkcja do wyświetlania listy unikalnych walut
def show_currencies(update: Update, context: CallbackContext) -> None:
    currencies = list(set(db.get_all_currencies()))  # Usunięcie duplikatów
    keyboard = [[KeyboardButton(currency)] for currency in currencies]
    keyboard.append([KeyboardButton("Wróć do menu głównego")])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    update.message.reply_text('Wybierz walutę, aby zobaczyć najlepsze kursy:', reply_markup=reply_markup)

# Metoda do wyświetlania najlepszego kursu dla waluty
def show_best_rate(update: Update, context: CallbackContext) -> None:
    currency = update.message.text
    best_rate = db.get_best_rate(currency)
    
    if best_rate['best_buy'] and best_rate['best_sell']:
        best_buy_name, best_buy_price, _ = best_rate['best_buy']
        best_sell_name, _, best_sell_price = best_rate['best_sell']
        
        response = f"""
        *Najlepsze kursy dla {currency}:*
        - 🏦 Najlepszy kurs zakup: {best_buy_name} — {best_buy_price}
        - 🏦 Najlepszy kurs sprzedaży: {best_sell_name} — {best_sell_price}
        """
    else:
        response = f"Brak danych o kursie dla {currency}."

    update.message.reply_text(response, parse_mode='Markdown')

# # Функция для показа кнопки "Wróć"
# def show_back_button(update: Update, context: CallbackContext) -> None:
#     keyboard = [[KeyboardButton("Wróć do kantora")]]
#     reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
#     update.message.reply_text("🔙 Aby wrócić, naciśnij 'Wróć do kantora'.", reply_markup=reply_markup)

# Obsługa komendy /start
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Witaj!👋 Cieszymy się, że tutaj jesteś! Nasz bot pomoże Ci znaleźć najlepsze kursy walut w kantorach.")
    show_main_menu(update, context)

# Obsługa głównego menu i wyboru waluty
def handle_main_menu_selection(update: Update, context: CallbackContext) -> None:
    selection = update.message.text
    if selection == "Kantors":
        show_kantors(update, context)
    elif selection == "Najlepszy kurs":
        show_currencies(update, context)
    elif selection == "Wróć do menu głównego":
        show_main_menu(update, context)
    elif selection in db.get_all_currencies():  # Sprawdzenie, czy wybrano walutę
        show_best_rate(update, context)
    elif selection in urls:  # Sprawdzenie, czy wybrano kantor
        handle_kantor_selection(update, context)
    else:
        update.message.reply_text("Proszę wybrać opcję z menu głównego.")

# Obsługa kantoru
def handle_kantor_selection(update: Update, context: CallbackContext) -> None:
    kantor_name = update.message.text
    if kantor_name in urls:
        url = urls[kantor_name]
        try:
            kantor_info = parse_kantor_data(url)
            update.message.reply_text(kantor_info, parse_mode='Markdown', disable_web_page_preview=True)
            # show_back_button(update, context)
        except Exception as e:
            logging.error(f"Błąd podczas przetwarzania kantoru {kantor_name}: {e}")
            update.message.reply_text("Wystąpił błąd podczas pobierania informacji. Spróbuj ponownie.")

def main():
    updater = Updater("7825220778:AAGin-KYB94veX0SSbS9BJn9qv3GNQ3JdAY", use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_main_menu_selection))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
