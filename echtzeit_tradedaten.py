import asyncio
import websockets
import json
import time

async def listen_trades_per_minute(symbol: str = "btcusdt"):
    """
    Abonniert den Echtzeit-Trades-Stream von Binance für das angegebene Symbol
    und aggregiert die Trades pro Minute.
    
    Es werden pro Minute:
      - Die Anzahl der Trades gezählt
      - Das gesamte gehandelte Volumen summiert
    """
    uri = f"wss://stream.binance.com:9443/ws/{symbol}@trade"
    async with websockets.connect(uri) as websocket:
        print(f"Verbunden mit dem Echtzeit-Trades-Stream für {symbol.upper()}!")
        
        trades = []            # Hier sammeln wir die Trade-Daten
        minute_start = time.time()  # Startzeit der aktuellen Minute

        while True:
            try:
                # Versuche, eine Nachricht zu empfangen (Timeout nach 1 Sekunde, um den Zeitcheck zu ermöglichen)
                message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                trade_data = json.loads(message)
                trades.append(trade_data)
            except asyncio.TimeoutError:
                # Kein Trade innerhalb von 1 Sekunde empfangen – fahren mit der Überprüfung fort
                pass
            
            current_time = time.time()
            if current_time - minute_start >= 60:
                # Aggregation der Trades der letzten Minute
                trade_count = len(trades)
                total_volume = sum(float(trade.get("q", 0)) for trade in trades)
                
                print(f"\n--- Zusammenfassung der letzten Minute ---")
                print(f"Anzahl Trades: {trade_count}")
                print(f"Gesamtvolumen: {total_volume}")
                print(f"------------------------------------------\n")
                
                # Zurücksetzen für die nächste Minute
                trades = []
                minute_start = current_time

if __name__ == "__main__":
    try:
        asyncio.run(listen_trades_per_minute("btcusdt"))
    except KeyboardInterrupt:
        print("Streaming beendet.")
