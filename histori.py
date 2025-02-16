import requests
import pandas as pd
import numpy as np
import time
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Globale Einstellungen
INTERVAL = '1d'         # Zeitrahmen für die Analyse
DATA_LIMIT = 500        # Anzahl der Datenpunkte
MAX_WORKERS = 5         # Parallelität für API Requests
MIN_SCORE = 7           # Mindestscore für die Filterung

def create_session():
    """Erstellt eine Session mit Retry-Logic"""
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=0.3,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

def get_binance_trading_pairs():
    """Hole alle aktiven USDT Trading-Paare"""
    session = create_session()
    url = "https://api.binance.com/api/v3/exchangeInfo"
    response = session.get(url)
    data = response.json()
    return [
        symbol['symbol'] for symbol in data['symbols']
        if symbol['status'] == 'TRADING' and symbol['symbol'].endswith("USDT")
    ]

def get_historical_data(symbol, interval=INTERVAL, limit=DATA_LIMIT):
    """Hole historische Kursdaten"""
    try:
        session = create_session()
        url = "https://api.binance.com/api/v3/klines"
        params = {'symbol': symbol, 'interval': interval, 'limit': limit}
        response = session.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ]).apply(pd.to_numeric)
        return df
    except Exception as e:
        print(f"Fehler bei {symbol}: {str(e)}")
        return None

def calculate_indicators(df):
    """Berechnung der technischen Indikatoren"""
    # Preprocessing
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[['timestamp', 'close', 'volume', 'quote_volume']].copy()
    
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
    df['macd_hist'] = df['macd'] - df['signal']
    
    # Moving Averages
    df['ma50'] = df['close'].rolling(50).mean()
    df['ma200'] = df['close'].rolling(200).mean()
    
    # Volumenanalyse
    df['vol_ma20'] = df['quote_volume'].rolling(20).mean()
    df['volume_pct'] = (df['quote_volume'] / df['vol_ma20'] - 1) * 100
    
    # Preismomentum
    df['momentum_7d'] = df['close'].pct_change(7) * 100
    df['momentum_30d'] = df['close'].pct_change(30) * 100
    
    # Trendstärke
    df['ma50_slope'] = df['ma50'].diff(5)
    df['rsi_slope'] = df['rsi'].diff(5)
    df['macd_hist_slope'] = df['macd_hist'].diff(3)
    df['volume_slope'] = df['quote_volume'].diff(3)
    
    # OBV (On-Balance Volume)
    df['obv'] = (np.sign(df['close'].diff()) * df['quote_volume']).fillna(0).cumsum()
    
    # Filter ungültiger Daten
    required_columns = ['ma50', 'ma200', 'rsi', 'macd', 'signal', 'vol_ma20']
    return df.dropna(subset=required_columns)

def calculate_score(df):
    """Berechnung des Bewertungsscores"""
    latest = df.iloc[-1]
    score = 0
    
    # Trend Score
    if latest['ma50'] > latest['ma200']:
        score += 3
    if latest['close'] > latest['ma50'] and latest['close'] > latest['ma200']:
        score += 2
    if latest['ma50_slope'] > 0:
        score += 1
    
    # Momentum Score
    if latest['macd_hist'] > 0:
        score += 2
    if latest['macd_hist_slope'] > 0:
        score += 1
    if 50 < latest['rsi'] < 70:
        score += 2
    elif latest['rsi'] >= 70:
        score -= 1
    if latest['rsi_slope'] > 0:
        score += 1
    
    # Volume Score
    if latest['volume_pct'] > 100:
        score += 3
    elif latest['volume_pct'] > 50:
        score += 2
    elif latest['volume_pct'] > 20:
        score += 1
    if latest['volume_slope'] > 0:
        score += 1
    
    # Momentum Score
    if latest['momentum_7d'] > 15:
        score += 3
    elif latest['momentum_7d'] > 10:
        score += 2
    elif latest['momentum_7d'] > 5:
        score += 1
    
    # OBV Trend
    if len(df) >= 10:
        obv_trend = df['obv'].iloc[-5:].mean() > df['obv'].iloc[-10:-5].mean()
        if obv_trend:
            score += 2
    
    return score

def analyze_symbol(symbol):
    """Analysiere ein einzelnes Symbol"""
    df = get_historical_data(symbol)
    if df is None or len(df) < 250:
        return None
    
    df = calculate_indicators(df)
    if df.empty:
        return None
    
    latest = df.iloc[-1]
    
    # Überprüfe auf fehlende Werte
    if any(pd.isna(v) for v in [latest['rsi'], latest['ma50'], latest['ma200']]):
        return None
    
    score = calculate_score(df)
    
    return {
        'symbol': symbol,
        'price': latest['close'],
        'rsi': round(latest['rsi'], 1),
        'macd_hist': round(latest['macd_hist'], 4),
        'volume_pct': round(latest['volume_pct'], 1),
        'momentum_7d': round(latest['momentum_7d'], 1),
        'ma50_slope': round(latest['ma50_slope'], 2),
        'score': score,
        'trend': 'Up' if latest['ma50'] > latest['ma200'] else 'Down'
    }

def main():
    """Hauptfunktion"""
    symbols = get_binance_trading_pairs()[:500]  # Analysiere erste 100 Coins
    
    print(f"Analysiere {len(symbols)} Coins...")
    results = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(analyze_symbol, sym) for sym in symbols]
        for i, future in enumerate(futures):
            try:
                result = future.result()
                if result and result['score'] >= MIN_SCORE:
                    results.append(result)
            except Exception as e:
                print(f"Fehler bei Verarbeitung: {str(e)}")
            
            # Rate Limit Management
            if (i + 1) % 10 == 0:
                time.sleep(1)
    
    # Sortiere Ergebnisse nach Score
    sorted_results = sorted(results, key=lambda x: x['score'], reverse=True)
    
    # Ausgabe der Top 15 Coins
    print("\nTop Kandidaten:")
    print(f"{'Symbol':<8} {'Preis':<10} {'Score':<6} {'RSI':<6} {'Vol%':<6} "
          f"{'M7d%':<6} {'MA50 Slope':<12} {'MACD Hist':<10} {'Trend'}")
    
    for coin in sorted_results[:15]:
        print(f"{coin['symbol']:<8} {coin['price']:<10.2f} {coin['score']:<6} "
              f"{coin['rsi']:<6.1f} {coin['volume_pct']:<6.1f} "
              f"{coin['momentum_7d']:<6.1f} {coin['ma50_slope']:<12.2f} "
              f"{coin['macd_hist']:<10.4f} {coin['trend']}")

if __name__ == "__main__":
    main()