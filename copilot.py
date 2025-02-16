import requests
import pandas as pd
from ta import momentum, trend, volatility
import numpy as np
from datetime import datetime
from backtesting import Backtest, Strategy

BINANCE_API_URL = "https://api.binance.com/api/v3"
FUTURES_API_URL = "https://fapi.binance.com/fapi/v1"

def safe_convert(value):
    """Konvertiert numpy- und Timestamp-Werte in native Python-Typen"""
    if isinstance(value, (np.generic, pd.Timestamp)):
        return float(value) if isinstance(value, np.floating) else str(value)
    return value

def get_binance_data(symbol, interval, limit=100):
    """Holt OHLCV-Daten und berechnet technische Indikatoren von Binance"""
    data = {}
    
    # OHLCV-Daten abrufen
    try:
        response = requests.get(f"{BINANCE_API_URL}/klines", params={
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        })
        ohlcv = response.json()
        
        df = pd.DataFrame(ohlcv, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades',
            'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        
        # Numerische Spalten konvertieren
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 
                        'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote']
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Entferne das 'ignore'-Feld
        df.drop(columns=['ignore'], inplace=True)
        
        # Überprüfe, ob zukünftige Daten vorhanden sind
        if df['timestamp'].max() > pd.Timestamp.now():
            raise ValueError("Future dates detected in OHLCV data!")
        
        data['ohlcv'] = df
        
    except Exception as e:
        print(f"OHLCV Fehler: {str(e)}")
        return None

    # Technische Indikatoren berechnen
    try:
        df = data['ohlcv'].copy()
        
        # RSI
        df['rsi'] = momentum.RSIIndicator(df['close'], window=14).rsi()
        
        # MACD
        macd = trend.MACD(df['close'])
        df['macd'] = macd.macd()
        df['signal'] = macd.macd_signal()
        
        # Moving Averages
        df['ma50'] = trend.SMAIndicator(df['close'], window=50).sma_indicator()
        # Berechne ma200 nur, wenn genügend Datenpunkte vorhanden sind
        if len(df) >= 200:
            df['ma200'] = trend.SMAIndicator(df['close'], window=200).sma_indicator()
        else:
            df['ma200'] = None
        
        # Bollinger Bands
        bb = volatility.BollingerBands(df['close'])
        df['upper'] = bb.bollinger_hband()
        df['middle'] = bb.bollinger_mavg()
        df['lower'] = bb.bollinger_lband()
        
        # ATR
        df['atr'] = volatility.AverageTrueRange(
            high=df['high'],
            low=df['low'],
            close=df['close'],
            window=14
        ).average_true_range()
        
        # Speichere die letzten Indikatorwerte (letzte Zeile)
        data['technical_indicators'] = df.iloc[-1].to_dict()
        
    except Exception as e:
        print(f"Indikator Fehler: {str(e)}")
    
    # Futures-Daten abrufen
    try:
        oi = requests.get(f"{FUTURES_API_URL}/openInterest", params={"symbol": symbol}).json()
        funding = requests.get(f"{FUTURES_API_URL}/fundingRate", params={"symbol": symbol}).json()
        data['futures'] = {
            'open_interest': oi,
            'funding_rate': funding
        }
    except Exception as e:
        print(f"Futures Fehler: {str(e)}")
    
    return data

def format_output(data):
    """Formatiert die Ausgabe korrekt für JSON"""
    # OHLCV-Daten vorbereiten
    ohlcv_data = data['ohlcv'].copy()
    ohlcv_data['timestamp'] = ohlcv_data['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # Technische Indikatoren formatieren und runden
    latest = data.get('technical_indicators', {})
    formatted_indicators = {
        "rsi": round(float(latest.get("rsi", 0)), 2) if latest.get("rsi") is not None else None,
        "macd_hist": round(float(latest.get("macd", 0)) - float(latest.get("signal", 0)), 2)
                     if (latest.get("macd") is not None and latest.get("signal") is not None) else None,
        "atr": round(float(latest.get("atr", 0)), 2) if latest.get("atr") is not None else None,
        "trend": "Bullish" if latest.get("close", 0) > latest.get("ma50", 0) else "Bearish"
    }
    
    # Futures-Daten formatieren
    futures = data.get("futures", {})
    open_interest = None
    funding_rate = None
    try:
        if "openInterest" in futures.get("open_interest", {}):
            open_interest = float(futures["open_interest"]["openInterest"])
    except Exception as e:
        print("Fehler beim Konvertieren von Open Interest:", e)
    try:
        if isinstance(futures.get("funding_rate"), list) and len(futures["funding_rate"]) > 0:
            funding_rate = round(float(futures["funding_rate"][-1]["fundingRate"]), 6)
    except Exception as e:
        print("Fehler beim Konvertieren von Funding Rate:", e)
    
    return {
        "technical_data": {
            "ohlcv": ohlcv_data.to_dict(orient='records'),
            "indicators": formatted_indicators
        },
        "market_sentiment": {
            "open_interest": open_interest,
            "funding_rate": funding_rate
        }
    }

# Backtesting-Strategie
class MyStrategy(Strategy):
    def init(self):
        # RSI-Indikator mit Talib
        self.rsi = self.I(talib.RSI, self.data.Close, 14)
        
    def next(self):
        # Kaufsignal, wenn RSI unter 30 liegt
        if self.rsi[-1] < 30:
            self.buy()

def run_backtest(df):
    """
    Führt ein Backtesting auf den OHLCV-Daten durch.
    Wichtige Anpassungen:
      - Umbenennung der Spalten für Backtesting (Open, High, Low, Close)
      - Setzen des Index als DatetimeIndex (falls 'timestamp' vorhanden)
      - Erhöhung des initialen Cash-Betrags
    """
    df_bt = df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close'})
    
    # Setze 'timestamp' als Index, falls vorhanden
    if 'timestamp' in df_bt.columns:
        df_bt.index = pd.to_datetime(df_bt['timestamp'])
    
    # Erhöhe den initialen Cash-Betrag (z. B. 50.000 statt 10.000)
    bt = Backtest(df_bt, MyStrategy, cash=50000, commission=0.002)
    return bt.run()


if __name__ == "__main__":
    symbol = "XRPUSDT"
    btc_data = get_binance_data(symbol=symbol, interval="30m", limit=100)
    if btc_data:
        analysis = format_output(btc_data)
        print(f"Analyseergebnisse: {symbol}")
        print(analysis)
        
        # Handelsentscheidung basierend auf RSI
        rsi_value = analysis["technical_data"]["indicators"].get("rsi")
        if rsi_value is not None and rsi_value < 30:
            print("KAUF-Signal: RSI unter 30")
        
        # Optional: Backtesting durchführen, sofern genügend Daten vorliegen
        try:
            df_for_backtest = btc_data["ohlcv"]
            backtest_results = run_backtest(df_for_backtest)
            print("Backtesting-Ergebnisse:")
            print(backtest_results)
        except Exception as e:
            print("Backtesting Fehler:", e)