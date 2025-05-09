# Hyperliquid Wallet Tracker

This script allows you to track transactions for a specific wallet address on Hyperliquid in real-time.

## Setup

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file (optional):
```bash
WALLET_ADDRESS=your_wallet_address_here
```

## Usage

Run the script:
```bash
python wallet_tracker.py
```

If you haven't set the wallet address in the `.env` file, the script will prompt you to enter it.

## Features

- Real-time tracking of trades
- Displays:
  - Timestamp
  - Coin being traded
  - Trade side (buy/sell)
  - Trade size
  - Trade price

## Notes

- The script uses Hyperliquid's WebSocket API for real-time updates
- It maintains a set of known trades to avoid duplicate notifications
- The connection will automatically attempt to reconnect if disconnected 