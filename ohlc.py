import requests
import datetime

def get_klines(symbol: str, interval: str, limit: int = 1):
    """
    Ruft Candlestick-Daten von Binance ab.
    
    :param symbol: Handelspaar, z.B. "BTCUSDT"
    :param interval: Zeitintervall, z.B. "30m" für 30 Minuten
    :param limit: Anzahl der Kerzen, die abgerufen werden sollen (Standard: 1)
    :return: Liste der Kerzen (Candlesticks)
    """
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    response = requests.get(url, params=params)
    response.raise_for_status()  # Bei HTTP-Fehlern eine Exception werfen
    return response.json()

def format_candle(candle: list) -> dict:
    """
    Formatiert eine Kerze in ein übersichtliches Dictionary.
    
    Die Binance API liefert jede Kerze als Liste mit folgender Struktur:
      0: Öffnungszeit (in Millisekunden)
      1: Open
      2: High
      3: Low
      4: Close
      5: Volume
      6: Schlusszeit (in Millisekunden)
      7: Quote Asset Volume
      8: Anzahl der Trades
      9: Taker Buy Base Asset Volume
      10: Taker Buy Quote Asset Volume
      11: Ignorierter Wert
    
    :param candle: Liste der Candlestick-Daten
    :return: Dictionary mit den gewünschten Informationen
    """
    open_time = datetime.datetime.fromtimestamp(candle[0] / 1000)
    close_time = datetime.datetime.fromtimestamp(candle[6] / 1000)
    
    return {
        "Open Time": open_time,
        "Open": candle[1],
        "High": candle[2],
        "Low": candle[3],
        "Close": candle[4],
        "Volume": candle[5],
        "Close Time": close_time,
        "Quote Asset Volume": candle[7],
        "Anzahl der Trades": candle[8]
    }

if __name__ == "__main__":
    symbol = "BTCUSDT"
    interval = "30m"  # 30-Minuten-Kerzen
    try:
        klines = get_klines(symbol, interval, limit=1)
        if klines:
            candle = format_candle(klines[0])
            print("Candlestick-Daten für", symbol)
            for key, value in candle.items():
                print(f"{key}: {value}")
        else:
            print("Keine Daten erhalten.")
    except requests.RequestException as e:
        print("Fehler beim Abruf der Daten:", e)
