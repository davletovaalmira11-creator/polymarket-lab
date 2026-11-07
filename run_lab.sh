#!/data/data/com.termux/files/usr/bin/bash
# Запуск всей экосистемы
nohup python3 /data/data/com.termux/files/home/AI_WORKSPACE/polymarket_lab/collector_fix.py > collector.log 2>&1 &
nohup python3 /data/data/com.termux/files/home/AI_WORKSPACE/polymarket_lab/lab_engine.py > lab.log 2>&1 &
nohup python3 /data/data/com.termux/files/home/AI_WORKSPACE/polymarket_lab/trading_bot.py > bot.log 2>&1 &
echo "System processes started."
