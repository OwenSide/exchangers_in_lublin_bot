import requests
from bs4 import BeautifulSoup
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
from apscheduler.schedulers.background import BackgroundScheduler
import logging
import pytz
import emoji
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from database import Database

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

db = Database()

scheduler = BackgroundScheduler()
timezone = pytz.timezone('Europe/Warsaw')

urls = {
    "🏆 Kantor Grand Olimp": "https://zlata.ws/pl/kantory/lublin/kantorgrandolimp/",
    "🚢 Kantor Korab": "https://zlata.ws/pl/kantory/lublin/kantorkorab/",
    "📜 1913 Kantor": "https://zlata.ws/pl/kantory/lublin/1913/",
    "🛡️ Kantor Tuus": "https://zlata.ws/pl/kantory/lublin/kantortuus/",
    "👩‍💼 Kantor Anna Janek": "https://zlata.ws/pl/kantory/lublin/kantorannajanek/",
    "💎 Kantor Paciorkowski": "https://zlata.ws/pl/kantory/lublin/paciorkowski/",
    "🌳 Kantor Witosa": "https://zlata.ws/pl/kantory/lublin/kantorzamkowy2/",
    "⛪ Kantor Probostwo": "https://zlata.ws/pl/kantory/lublin/kantorzamkowy1/",
    "🏙️ Kantor Tarasy": "https://zlata.ws/pl/kantory/lublin/kantortarasylublin/",
    "🎨 Kantor Grazyna": "https://zlata.ws/pl/kantory/lublin/kantorygrazynalublin/",
    "🏖️ Kantor Plaza": "https://zlata.ws/pl/kantory/lublin/kantorplazalublin/"
}

currency_emojis = {
    '1 USD': '🇺🇸', '1 EUR': '🇪🇺', '1 GBP': '🇬🇧', '1 CHF': '🇨🇭', '1 CAD': '🇨🇦',
    '1 AUD': '🇦🇺', '1 DKK': '🇩🇰', '1 CZK': '🇨🇿', '1 HUF': '🇭🇺', '1 BGN': '🇧🇬',
    '1 UAH': '🇺🇦', '1 ILS': '🇮🇱', '1 JPY': '🇯🇵', '1 RON': '🇷🇴', '1 TRY': '🇹🇷',
    '1 NOK': '🇳🇴', '1 SEK': '🇸🇪', '1 RUB': '🇷🇺', '1 CNY': '🇨🇳', '1 HKD': '🇭🇰',
    '1 ISK': '🇮🇸', '1 ALL': '🇦🇱', '1 AED': '🇦🇪', '1 GEL': '🇬🇪', '1 THB': '🇹🇭',
    '1 RSD': '🇷🇸', '1 BAM': '🇧🇦', '1 EGP': '🇪🇬', '1 MKD': '🇲🇰', '1 KRW': '🇰🇷',
    '1 MYR': '🇲🇾', '1 MXN': '🇲🇽',
}

# Metoda odpowiada za pobieranie współrzędnych geograficznych na podstawie adresu za pomocą geolokatora.
def get_coordinates_from_address(address: str):
    geolocator = Nominatim(user_agent="OwenSide")
    location = geolocator.geocode(address)

    if location:
        return location.latitude, location.longitude
    else:
        return None, None

# Metoda analizuje dane z podanej strony kantoru i zwraca sformatowane informacje w postaci tekstu.
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

    latitude, longitude = get_coordinates_from_address(address)

    table = soup.find('table', class_='table')
    rows = table.find_all('tr')[1:]
    currencies_info = []

    for row in rows:
        cols = row.find_all('td')
        currency_name = cols[0].text.strip().split("\n")[0].strip()
        buy_price = float(cols[1].text.strip())
        sell_price = float(cols[2].text.strip())
    
        if name in ["Kantor Witosa", "Kantor Probostwo"]:
            buy_price /= 100
            sell_price /= 100

        emoji = currency_emojis.get(currency_name, '💱') 

        currency_info = f"{emoji} *{currency_name}*: {buy_price} / {sell_price}"
        currencies_info.append(currency_info)

        clean_currency_info = f"{currency_name}: {buy_price} / {sell_price}"

        currency_data = clean_currency_info.split(': ')
        if len(currency_data) == 2:
            currency, prices = currency_data
            buy_price, sell_price = prices.split(' / ')
            db.update_exchange_rate(name, currency, buy_price, sell_price, address, latitude, longitude, comment)

    update_time = update_time.replace("в", "w")
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

# Metoda odpowiada za aktualizowanie danych wszystkich kantorów w regularnych odstępach czasowych.
def update_all_kantors():
    for kantor_name, url in urls.items():
        try:
            kantor_info = parse_kantor_data(url)
        except Exception as e:
            logging.error(f"Błąd podczas przetwarzania kantoru {kantor_name}: {e}")

    
    scheduler.add_job(update_all_kantors, 'interval', minutes=30, timezone=timezone)
    scheduler.start()
update_all_kantors()

 # Metoda wyświetla główne menu użytkownikowi z opcjami wyboru.
def show_main_menu(update: Update, context: CallbackContext) -> None:
    context.user_data['message_shown'] = False
    keyboard = [
        [KeyboardButton("💱 Kantors")],
        [KeyboardButton("📈 Najlepszy kurs")],
        [KeyboardButton("📍 Znajdź najbliższy kantor", request_location=True)] 
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    update.message.reply_text('📋 Wybierz opcję z menu głównego:', reply_markup=reply_markup)

# Metoda wyświetla listę dostępnych kantorów, które użytkownik może wybrać.
def show_kantors(update: Update, context: CallbackContext) -> None:
    keyboard = [[KeyboardButton(name)] for name in urls.keys()]
    keyboard.append([KeyboardButton("⬅️ Wróć do menu głównego")])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    update.message.reply_text('🏦 Wybierz kantor:', reply_markup=reply_markup)

# Metoda wyświetla listę dostępnych walut, umożliwiając użytkownikowi wybór interesującej go waluty.
def show_currencies(update: Update, context: CallbackContext) -> None:
    selected_currency = update.message.text if 'selected_currency' not in context.user_data else context.user_data['selected_currency']
    currencies = list(set(db.get_all_currencies()))

    if not currencies:
        update.message.reply_text("Brak dostępnych walut.")
        return

    priority_currencies = ['1 USD', '1 EUR', '1 GBP', '1 CHF', '1 UAH']

    sorted_currencies = sorted(
        currencies,
        key=lambda x: (x not in priority_currencies, priority_currencies.index(x) if x in priority_currencies else float('inf'))
    )

    keyboard = []
    row = []

    for currency in sorted_currencies:
        emoji = currency_emojis.get(currency, '💱') 
        button_text = f"{emoji} {currency}"

        row.append(KeyboardButton(button_text))

        if len(row) == 3:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([KeyboardButton("⬅️ Wróć do menu głównego")])

    if not context.user_data.get('message_shown', False):
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        update.message.reply_text('💱 Wybierz walutę, aby zobaczyć najlepsze kursy:', reply_markup=reply_markup)
        context.user_data['message_shown'] = True

# Metoda pokazuje najlepszy kurs zakupu i sprzedaży dla wybranej waluty wraz z dodatkowymi szczegółami.
def show_best_rate(update: Update, context: CallbackContext) -> None:
    currency = clean_currency_name(update.message.text) 
    best_rate = db.get_best_rate(currency)
    all_rates = db.get_all_rates_with_address(currency) 

    if best_rate['best_buy'] and best_rate['best_sell']:
        best_buy_name, best_buy_price, _, best_buy_address = best_rate['best_buy']
        best_sell_name, _, best_sell_price, best_sell_address = best_rate['best_sell']
        
        best_buy_map_link = f"https://www.google.com/maps/search/?api=1&query={best_buy_address.replace(' ', '+')}"
        best_sell_map_link = f"https://www.google.com/maps/search/?api=1&query={best_sell_address.replace(' ', '+')}"
        
        response = (
            f"*Najlepsze kursy dla {currency}:*\n"
            f"- 🏦 Najlepszy kurs zakup: \n \u2003[{best_buy_name}]({best_buy_map_link}) — {best_buy_price}\n"
            f"- 🏦 Najlepszy kurs sprzedaży: \n \u2003[{best_sell_name}]({best_sell_map_link}) — {best_sell_price}\n"
            f"\n*Wszystkie dostępne kursy dla {currency}:*"
        )
        for rate in all_rates:
            name, buy_price, sell_price, address = rate
            maps_link = f"https://www.google.com/maps/search/?api=1&query={address.replace(' ', '+')}"
            response += f"\n- 🏦 [{name}]({maps_link}): {buy_price} / {sell_price}"
    else:
        response = f"Brak danych o kursie dla {currency}."

    update.message.reply_text(response, parse_mode='Markdown', disable_web_page_preview=True)

# Metoda prosi użytkownika o wysłanie swojej lokalizacji, aby znaleźć najbliższy kantor.
def request_user_location(update: Update, context: CallbackContext) -> None:
    keyboard = [[KeyboardButton("📍 Wyślij moją lokalizację", request_location=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    update.message.reply_text("📍 Proszę wyślij swoją lokalizację, aby znaleźć najbliższy kantor.", reply_markup=reply_markup)

# Metoda znajduje najbliższy kantor w stosunku do lokalizacji użytkownika, obliczając odległość.
def find_nearest_kantor(user_location):
    user_coords = (user_location.latitude, user_location.longitude)
        
    db.cursor.execute('SELECT name, address, latitude, longitude FROM exchange_rates')
    kantors = db.cursor.fetchall()

    nearest_kantor = None
    nearest_distance = float('inf')

    for kantor in kantors:
        kantor_name, kantor_address, latitude, longitude = kantor
        kantor_coords = (latitude, longitude)
        distance = geodesic(user_coords, kantor_coords).kilometers
            
        if distance < nearest_distance:
            nearest_distance = distance
            nearest_kantor = (kantor_name, kantor_address, distance)
        
    return nearest_kantor

# Metoda obsługuje lokalizację przesłaną przez użytkownika i wyświetla najbliższy kantor wraz z informacjami.
def handle_location(update: Update, context: CallbackContext) -> None:
    user_location = update.message.location
    if not user_location:
        update.message.reply_text("Nie udało się uzyskać lokalizacji. Proszę spróbować ponownie.")
        return

    nearest_kantor = find_nearest_kantor(user_location)
    
    if nearest_kantor:
        kantor_name, kantor_address, distance = nearest_kantor
        
        db = Database()

        exchange_rates = db.get_rates_for_kantor(kantor_name)

        priority_currencies = ['1 USD', '1 EUR', '1 GBP', '1 CHF', '1 UAH']

        sorted_exchange_rates = sorted(
            exchange_rates, 
            key=lambda x: (x[0] not in priority_currencies, priority_currencies.index(x[0]) if x[0] in priority_currencies else float('inf'))
        )

        currency_info_text = "\n".join([
            f"{currency_emojis.get(currency, '💱')} *{currency}*: {buy} / {sell}"
            for currency, buy, sell, _, comment in sorted_exchange_rates
        ])

        comment_text = sorted_exchange_rates[0][4].strip() if sorted_exchange_rates and sorted_exchange_rates[0][4].strip() else "Brak"
 
        maps_link = f"https://www.google.com/maps/search/?api=1&query={kantor_address.replace(' ', '+')}"

        response = (
            f"*Najbliższy kantor:*\n"
            f"🏦 *Nazwa:* [{kantor_name}]({maps_link})\n"
            f"📍 *Adres:* {kantor_address}\n"
            f"📏 *Odległość:* {distance:.2f} km\n"
            f"*💱 Kursy walut (Kupno/Sprzedaż):*\n"
            f"{currency_info_text}\n"
            f"*📋 Komentarz:* {comment_text}"
        )
    else:
        response = "Niestety, nie ma żadnych kantorów w pobliżu."


    update.message.reply_text(response, parse_mode='Markdown', disable_web_page_preview=True)

# Metoda usuwa emotikony i nadmiarowe znaki z nazwy waluty, aby uzyskać czysty tekst.
def clean_currency_name(currency_name):
    cleaned_name = emoji.replace_emoji(currency_name, replace='').strip()
    return cleaned_name

# Metoda obsługuje wybór użytkownika z głównego menu i przekierowuje do odpowiednich funkcji.
def handle_main_menu_selection(update: Update, context: CallbackContext) -> None:
    selection = update.message.text
    selection_cleaned = clean_currency_name(selection) 

    if selection == "💱 Kantors":
        show_kantors(update, context)
    elif selection == "📈 Najlepszy kurs":
        show_currencies(update, context)
    elif selection == "⬅️ Wróć do menu głównego":
        show_main_menu(update, context)
    elif selection_cleaned in db.get_all_currencies():  
        context.user_data['selected_currency'] = selection_cleaned  
        show_best_rate(update, context)
        show_currencies(update, context)
    elif selection in urls:
        handle_kantor_selection(update, context)
    else:
        update.message.reply_text("📋 Proszę wybrać opcję z menu głównego.")

# Metoda obsługuje wybór konkretnego kantoru i wyświetla jego szczegóły.
def handle_kantor_selection(update: Update, context: CallbackContext) -> None:
    kantor_name = update.message.text
    if kantor_name in urls:
        url = urls[kantor_name]
        try:
            kantor_info = parse_kantor_data(url)
            update.message.reply_text(kantor_info, parse_mode='Markdown', disable_web_page_preview=True)
        except Exception as e:
            logging.error(f"Błąd podczas przetwarzania kantoru {kantor_name}: {e}")
            update.message.reply_text("Wystąpił błąd podczas pobierania informacji. Spróbuj ponownie.")

# Metoda obsługuje komendę start i wita użytkownika, a następnie pokazuje główne menu.
def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Witaj!👋 Cieszymy się, że tutaj jesteś! Nasz bot pomoże Ci znaleźć najlepsze kursy walut w kantorach.")
    show_main_menu(update, context)

 # Metoda główna odpowiada za konfigurację bota i uruchomienie jego funkcji.
def main():
    updater = Updater("7825220778:AAGin-KYB94veX0SSbS9BJn9qv3GNQ3JdAY", use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.location, handle_location))  
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_main_menu_selection))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
