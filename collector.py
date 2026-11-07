import requests
import csv
import time
import os
from datetime import datetime

# Мониторим рынки (замените ID на актуальные из scanner.py)
MARKETS_TO_WATCH = ['559651', '559652'] 
FILE_DIR = "/data/data/com.termux/files/home/AI_WORKSPACE/polymarket_scanner/data"

if not os.path.exists(FILE_DIR):
    os.makedirs(FILE_DIR)

def log_market_data():
    url = "https://gamma-api.polymarket.com/markets"
    
    for market_id in MARKETS_TO_WATCH:
        try:
            response = requests.get(f"{url}/{market_id}")
            market = response.json()
            
            # Парсинг цен из строки "['0.1', '0.9']"
            outcome_prices = market.get('outcomePrices', '["0", "0"]').strip('[]').replace('"', '').split(',')
            prices = [float(p) for p in outcome_prices]
            
            file_path = os.path.join(FILE_DIR, f"market_{market_id}.csv")
            
            # Пишем заголовок, если файл пуст
            file_exists = os.path.isfile(file_path)
            with open(file_path, 'a', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(['timestamp', 'yes_price', 'no_price', 'volume24h'])
                
                writer.writerow([
                    datetime.now().isoformat(),
                    prices[0],
                    prices[1],
                    market.get('volume24hr', 0)
                ])
        except Exception as e:
            print(f"Error logging market {market_id}: {e}")

if __name__ == "__main__":
    print("Collector started. Logging data...")
    while True:
        log_market_data()
        time.sleep(300) # 5 минут
