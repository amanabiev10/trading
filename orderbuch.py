import requests

def get_order_book(symbol: str, limit: int = 10) -> dict:
    """
    Ruft Orderbuch-Daten von Binance ab.

    :param symbol: Handelspaar, z.B. "BTCUSDT"
    :param limit: Anzahl der Orderbuch-Einträge, z.B. 10 (Standard: 10)
    :return: Dictionary mit den Orderbuch-Daten (Bids und Asks)
    """
    url = "https://api.binance.com/api/v3/depth"
    params = {
        "symbol": symbol,
        "limit": limit
    }
    response = requests.get(url, params=params)
    response.raise_for_status()  # Bei HTTP-Fehlern wird eine Exception geworfen
    return response.json()

def print_order_book(order_book: dict):
    """
    Gibt die Orderbuch-Daten aus:
    - Aktuelle Top Bid- und Ask-Preise
    - Orderbuchtiefe der Bids und Asks
    """
    bids = order_book.get("bids", [])
    asks = order_book.get("asks", [])
    
    if bids:
        top_bid_price, top_bid_qty = bids[0]
    else:
        top_bid_price, top_bid_qty = None, None

    if asks:
        top_ask_price, top_ask_qty = asks[0]
    else:
        top_ask_price, top_ask_qty = None, None
    
    print("Aktueller Orderbuch-Status:")
    print(f"Top Bid: Preis = {top_bid_price}, Menge = {top_bid_qty}")
    print(f"Top Ask: Preis = {top_ask_price}, Menge = {top_ask_qty}\n")
    
    print("Orderbuchtiefe (Bids):")
    for bid in bids:
        price, qty = bid
        print(f"Preis: {price}, Menge: {qty}")
    
    print("\nOrderbuchtiefe (Asks):")
    for ask in asks:
        price, qty = ask
        print(f"Preis: {price}, Menge: {qty}")

if __name__ == "__main__":
    symbol = "BTCUSDT"
    try:
        order_book = get_order_book(symbol, limit=10)  # Hole die Top 10 Einträge
        print_order_book(order_book)
    except requests.RequestException as e:
        print("Fehler beim Abruf der Orderbuch-Daten:", e)
