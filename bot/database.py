import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_name='exchange_rates.db'):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS exchange_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                currency TEXT,
                buy_price REAL,
                sell_price REAL,
                last_update DATETIME,
                UNIQUE(name, currency)  -- Уникальное ограничение на кантор и валюту
            )
        ''')
        self.conn.commit()

    def update_exchange_rate(self, name, currency, buy_price, sell_price):
        currency = currency.strip('*')  
        now = datetime.now()
        self.cursor.execute('''
            INSERT OR REPLACE INTO exchange_rates (name, currency, buy_price, sell_price, last_update)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, currency, buy_price, sell_price, now))
        self.conn.commit()


    def get_best_rate(self, currency):
        self.cursor.execute('''
            SELECT name, buy_price, sell_price 
            FROM exchange_rates 
            WHERE currency = ? 
            ORDER BY buy_price DESC 
            LIMIT 1
        ''', (currency,))
        best_buy = self.cursor.fetchone()

        self.cursor.execute('''
            SELECT name, buy_price, sell_price 
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


    def get_all_currencies(self):
        self.cursor.execute('SELECT DISTINCT currency FROM exchange_rates')
        return [row[0] for row in self.cursor.fetchall()]


    def close(self):
        self.conn.close()
