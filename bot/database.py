import sqlite3
from datetime import datetime

class Database:
    """
    Inicjalizuje połączenie z bazą danych SQLite o nazwie podanej w parametrze.
    Tworzy tabelę, jeśli jeszcze nie istnieje.
    """
    def __init__(self, db_name='exchange_rates.db'):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_table()

    """
    Tworzy tabelę 'exchange_rates', jeśli jeszcze nie istnieje.
    Tabela przechowuje informacje o kursach walut, adresach kantorów i komentarzach.
    """
    def create_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS exchange_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                currency TEXT,
                buy_price REAL,
                sell_price REAL,
                last_update DATETIME,
                address TEXT,
                latitude REAL,
                longitude REAL,
                comment TEXT,
                UNIQUE(name, currency)
            )
        ''')
        self.conn.commit()


    """
    Aktualizuje lub dodaje kurs wymiany dla określonego kantoru i waluty.
    Jeśli wpis dla danej waluty i kantoru już istnieje, zostaje zastąpiony nowymi danymi.
        
    Argumenty:
    - name: Nazwa kantoru
    - currency: Kod waluty (np. USD, EUR)
    - buy_price: Cena zakupu waluty
    - sell_price: Cena sprzedaży waluty
    - address: Adres kantoru
    - latitude: Szerokość geograficzna kantoru
    - longitude: Długość geograficzna kantoru
    - comment: Opcjonalny komentarz dotyczący kursu lub kantoru
    """
    def update_exchange_rate(self, name, currency, buy_price, sell_price, address, latitude, longitude, comment):
        currency = currency.strip('*')
        now = datetime.now()
        self.cursor.execute(''' 
            INSERT OR REPLACE INTO exchange_rates (name, currency, buy_price, sell_price, address, latitude, longitude, comment, last_update) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) 
        ''', (name, currency, buy_price, sell_price, address, latitude, longitude, comment, now))
        self.conn.commit()

    def get_all_rates_with_address(self, currency):
        self.cursor.execute('''
            SELECT name, buy_price, sell_price, address
            FROM exchange_rates
            WHERE currency = ?
        ''', (currency,))
        return self.cursor.fetchall()

    def get_rates_for_kantor(self, kantor_name):
        self.cursor.execute(''' 
            SELECT currency, buy_price, sell_price, address, comment
            FROM exchange_rates 
            WHERE name = ?
        ''', (kantor_name,))
        return self.cursor.fetchall()


    """
    Znajduje najlepszy kurs zakupu (najwyższy) i sprzedaży (najniższy) dla podanej waluty.
    
    Argumenty:
    - currency: Kod waluty (np. USD, EUR).
        
    Zwraca:
    Słownik z najlepszym kursem zakupu ('best_buy') i sprzedaży ('best_sell'),
    każdy zawiera dane: (name, buy_price, sell_price, address).
    """
    def get_best_rate(self, currency):
        self.cursor.execute(''' 
            SELECT name, buy_price, sell_price, address 
            FROM exchange_rates 
            WHERE currency = ? 
            ORDER BY buy_price DESC 
            LIMIT 1
        ''', (currency,))
        best_buy = self.cursor.fetchone()

        self.cursor.execute(''' 
            SELECT name, buy_price, sell_price, address 
            FROM exchange_rates 
            WHERE currency = ? 
            ORDER BY sell_price ASC 
            LIMIT 1
        ''', (currency,))
        best_sell = self.cursor.fetchone()

        return {
            'best_buy': best_buy,
            'best_sell': best_sell
        }

    """
    Pobiera unikalną listę wszystkich walut dostępnych w bazie danych.
        
    Zwraca:
    Lista kodów walut (np. ['USD', 'EUR', 'GBP']).
    """
    def get_all_currencies(self):
        
        self.cursor.execute('SELECT DISTINCT currency FROM exchange_rates')
        return [row[0] for row in self.cursor.fetchall()]

    """
    Zamknięcie połączenia z bazą danych.
    """
    def close(self):
        self.conn.close()