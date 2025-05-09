import psycopg2
import requests
from datetime import datetime

# CONFIG
DB_CONN = "dbname=wallet_tracker user=postgres password="" host=localhost"
WALLETS = [
    # Add your wallet addresses here
    "0x6c92461130429ed99fe6c7c453410bb70ff26e6e",
    "0x55999a9124b976d05a7fd98d414e185d95e9e940",
    "0xf47249e6a3d1326439316f23081810094be53bfc"
]
API_BASE = "http://127.0.0.1:8080"  # Your Flask API base

def fetch_wallet_state(address):
    # Get user state (for unrealized PnL and account value)
    resp = requests.get(f"{API_BASE}/api/user_state?address={address}")
    data = resp.json()
    margin = data.get("marginSummary", {})
    unrealized_pnl = sum(float(pos["position"].get("unrealizedPnl", 0)) for pos in data.get("assetPositions", []))
    account_value = float(margin.get("accountValue", 0))
    # Get realized PnL (sum of closed positions, e.g. last 30d)
    resp2 = requests.get(f"{API_BASE}/api/pnl_timeseries?address={address}")
    pnl_data = resp2.json()
    realized_pnl = sum(day.get("cum_pnl_30d", 0) for day in pnl_data[-1:]) if pnl_data else 0
    # Compute ROE
    roe = (realized_pnl + unrealized_pnl) / account_value if account_value else 0
    return realized_pnl, unrealized_pnl, account_value, roe

def store_snapshot(conn, address, realized_pnl, unrealized_pnl, account_value, roe):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO wallet_snapshots
            (wallet_address, timestamp, realized_pnl, unrealized_pnl, account_value, roe)
            VALUES (%s, %s, %s, %s, %s, %s)""",
            (address, datetime.utcnow(), realized_pnl, unrealized_pnl, account_value, roe)
        )
    conn.commit()

def main():
    conn = psycopg2.connect(DB_CONN)
    for address in WALLETS:
        realized_pnl, unrealized_pnl, account_value, roe = fetch_wallet_state(address)
        store_snapshot(conn, address, realized_pnl, unrealized_pnl, account_value, roe)
        print(f"Stored snapshot for {address} at {datetime.utcnow()}")
    conn.close()

if __name__ == "__main__":
    main() 