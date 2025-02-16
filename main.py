# Ersetze diese Werte durch deinen eigenen API-Key und Secret!
from dotenv import load_dotenv
import os
import requests
import pandas as pd
import numpy as np
import time
from concurrent.futures import ThreadPoolExecutor
# .env-Datei laden
load_dotenv()

# Werte aus der .env-Datei abrufen
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

def get_binance_trading_pairs():
    url = "https://api.binance.com/api/v3/exchangeInfo"
    response = requests.get(url)
    data = response.json()
    return [symbol['symbol'] for symbol in data['symbols'] if symbol['status'] == 'TRADING' and symbol['symbol'].endswith("USDT")]

def get_historical_data(symbol, interval='1h', limit=200):
    try:
        url = "https://api.binance.com/api/v3/klines"
        params = {'symbol': symbol, 'interval': interval, 'limit': limit}
        data = requests.get(url, params=params).json()
        return pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ]).apply(pd.to_numeric)
    except Exception as e:
        print(f"Fehler bei {symbol}: {str(e)}")
        return None

def calculate_indicators(df):
    # Preprocessing
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[['timestamp', 'close', 'volume']].copy()
    
    # RSI
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # MACD
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = ema12 - ema26
    df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    
    # Moving Averages
    df['ma50'] = df['close'].rolling(50).mean()
    df['ma200'] = df['close'].rolling(200).mean()
    
    # Volume Analysis
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['volume_pct'] = (df['volume'] / df['vol_ma20'] - 1) * 100
    
    # Price Momentum
    df['momentum_24h'] = (df['close'].pct_change(24) * 100)
    
    return df.dropna()

def calculate_score(df):
    latest = df.iloc[-1]
    score = 0
    
    # Trend Score
    if latest['ma50'] > latest['ma200']:
        score += 2
    if latest['close'] > latest['ma50']:
        score += 1
        
    # Momentum Score
    if latest['macd'] > latest['signal']:
        score += 2
    if latest['rsi'] > 50 and latest['rsi'] < 70:
        score += 1
    if latest['momentum_24h'] > 5:
        score += 2
        
    # Volume Score
    if latest['volume_pct'] > 50:
        score += 3
    elif latest['volume_pct'] > 30:
        score += 2
    elif latest['volume_pct'] > 20:
        score += 1
        
    return score

def analyze_symbol(symbol):
    df = get_historical_data(symbol)
    if df is None or len(df) < 200:
        return None
    
    df = calculate_indicators(df)
    if len(df) < 1:
        return None
    
    latest = df.iloc[-1]
    score = calculate_score(df)
    
    return {
        'symbol': symbol,
        'price': latest['close'],
        'rsi': round(latest['rsi'], 1),
        'macd_hist': latest['macd'] - latest['signal'],
        'volume_change': round(latest['volume_pct'], 1),
        'momentum_24h': round(latest['momentum_24h'], 1),
        'score': score,
        'trend': 'Up' if latest['ma50'] > latest['ma200'] else 'Down'
    }

def main():
    symbols = get_binance_trading_pairs()[:100]  # Teste erst 100 Coins
    
    print("Analysiere Coins...")
    results = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(analyze_symbol, sym) for sym in symbols]
        for future in futures:
            result = future.result()
            if result and result['score'] > 5:
                results.append(result)
            time.sleep(0.1)
    
    # Sortiere Ergebnisse nach Score
    sorted_results = sorted(results, key=lambda x: x['score'], reverse=True)
    
    # Ausgabe der Top 10 Coins
    print("\nTop Kandidaten:")
    print(f"{'Symbol':<10} {'Preis':<10} {'Score':<6} {'RSI':<6} {'Vol+%':<6} {'Momentum':<8} {'Trend'}")
    for coin in sorted_results[:10]:
        print(f"{coin['symbol']:<10} {coin['price']:<10.2f} {coin['score']:<6} "
              f"{coin['rsi']:<6.1f} {coin['volume_change']:<6.1f} "
              f"{coin['momentum_24h']:<8.1f} {coin['trend']}")

if __name__ == "__main__":
    main()