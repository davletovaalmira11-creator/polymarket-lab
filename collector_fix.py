import requests
import csv
import time
import os
from datetime import datetime

MARKETS_TO_WATCH = ['559651', '559652', '559653', '559654', '559655']
FILE_DIR = "/data/data/com.termux/files/home/AI_WORKSPACE/polymarket_lab/data"

if not os.path.exists(FILE_DIR):
    os.makedirs(FILE_DIR)

def log_market_data():
    url = "https://gamma-api.polymarket.com/markets"
    for market_id in MARKETS_TO_WATCH:
        try:
            response = requests.get(f"{url}/{market_id}", timeout=10)
            market = response.json()
            outcome_prices = market.get('outcomePrices', '["0", "0"]').strip('[]').replace('"', '').split(',')
            prices = [float(p) for p in outcome_prices]
            best_bid = float(market.get('bestBid', 0))
            best_ask = float(market.get('bestAsk', 0))
            file_path = os.path.join(FILE_DIR, f"market_{market_id}.csv")
            file_exists = os.path.isfile(file_path)
            with open(file_path, 'a', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(['timestamp', 'yes_price', 'no_price', 'best_bid', 'best_ask', 'volume24h'])
                writer.writerow([datetime.now().isoformat(), prices[0], prices[1], best_bid, best_ask, market.get('volume24hr', 0)])
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    while True:
        log_market_data()
        time.sleep(60)
