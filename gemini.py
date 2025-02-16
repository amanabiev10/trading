import requests
import pandas as pd
from ta import momentum, trend, volatility
import numpy as np
from datetime import datetime
from backtesting import Backtest, Strategy
from ta import momentum, trend, volatility
import talib  # Importiere talib

BINANCE_API_URL = "https://api.binance.com/api/v3"
FUTURES_API_URL = "https://fapi.binance.com/fapi/v1"

def get_binance_data(symbol, interval, limit=100):
    """Holt OHLCV-Daten und berechnet technische Indikatoren von Binance."""
    data = {}

    try:
        # OHLCV-Daten abrufen
        response = requests.get(f"{BINANCE_API_URL}/klines", params={
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        })
        response.raise_for_status()  # Überprüfe auf HTTP-Fehler (4xx oder 5xx)
        ohlcv = response.json()

        df = pd.DataFrame(ohlcv, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])

        # Numerische Spalten konvertieren
        numeric_cols = ['open', 'high', 'low', 'close', 'volume',
                        'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote']
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric)

        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # Überprüfe, ob zukünftige Daten vorhanden sind (optional)
        if df['timestamp'].max() > pd.Timestamp.now():
            raise ValueError("Future dates detected in OHLCV data!")

        data['ohlcv'] = df

    except requests.exceptions.RequestException as e:
        print(f"OHLCV Fehler (HTTP): {e}")
        return None
    except (ValueError, TypeError) as e:  # Fange Konvertierungsfehler ab
        print(f"OHLCV Fehler (Datenverarbeitung): {e}")
        return None
    except Exception as e:
        print(f"OHLCV Fehler: {str(e)}")
        return None


    try:
        df = data['ohlcv'].copy()

        # RSI mit talib (schneller und zuverlässiger)
        df['rsi'] = talib.RSI(df['close'], timeperiod=14)

        # MACD mit talib
        macd, macdsignal, macdhist = talib.MACD(df['close'], fastperiod=12, slowperiod=26, signalperiod=9)
        df['macd'] = macd
        df['signal'] = macdsignal
        df['macd_hist'] = macdhist  # Füge die Histogramm-Daten hinzu

        # Moving Averages mit talib
        df['ma50'] = talib.SMA(df['close'], timeperiod=50)
        df['ma200'] = talib.SMA(df['close'], timeperiod=200) if len(df) >= 200 else None

        # Bollinger Bands mit talib
        upper, middle, lower = talib.BBANDS(df['close'], timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
        df['upper'] = upper
        df['middle'] = middle
        df['lower'] = lower

        # ATR mit talib
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)

        data['technical_indicators'] = df.iloc[-1].to_dict()

    except Exception as e:
        print(f"Indikator Fehler: {str(e)}")
        return None  # Gib None zurück, wenn ein Fehler auftritt

    # ... (Rest des Codes bleibt im Wesentlichen gleich)

# ... (format_output und andere Funktionen)

if __name__ == "__main__":
    # ... (Code zum Abrufen und Verarbeiten der Daten)