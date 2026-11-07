import requests
import time
import json
import os

STRATEGY_FILE = "best_strategy.json"
PAPER_TRADES_FILE = "paper_trades.json"

def get_market_data(market_id):
    url = f"https://gamma-api.polymarket.com/markets/{market_id}"
    response = requests.get(url)
    return response.json()

def run_bot():
    if not os.path.exists(STRATEGY_FILE): return
    
    with open(STRATEGY_FILE, 'r') as f:
        strategy = json.load(f)
        
    print("Bot started...")
    position = 0 # 0: None, 1: Yes
    entry_price = 0
    balance = 1000.0
    
    while True:
        try:
            data = get_market_data(strategy['market_id'])
            outcome_prices = data.get('outcomePrices', '["0", "0"]').strip('[]').replace('"', '').split(',')
            yes_price = float(outcome_prices[0])
            no_price = float(outcome_prices[1])
            sum_price = yes_price + no_price
            
            if True and position == 0:
                position = 1
                entry_price = yes_price
                print(f"Bought Yes at {entry_price}")
            elif position == 1 and (sum_price > 0.98 or yes_price > entry_price * 1.02):
                profit = (yes_price - entry_price) * 100
                balance += profit
                position = 0
                print(f"Sold Yes at {yes_price}. Profit: {profit}")
                with open(PAPER_TRADES_FILE, 'w') as f:
                    json.dump({'balance': balance, 'last_profit': profit}, f)
                    
            time.sleep(60)
        except Exception as e:
            print(f"Bot error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_bot()
