# Hyperliquid Wallet Tracker

A comprehensive tool for tracking and analyzing Hyperliquid wallet trades with real-time and historical trade data analysis.

## Features

### Account Overview
- Account total value display
- Withdrawable balance
- Total margin usage
- Total position value
- Current position details with entry prices, leverage, and ROE

### Trade History
- Query trades by wallet address
- Filter by date range
- Filter by coin and trade size
- Sort by timestamp, size, price, or PnL
- View merged trades by hour
- Save favorite wallet addresses with tags
- Cryptocurrency price history charts with trade point markers

### PnL Analysis
- Cumulative PnL charts with timeframe selection
- Winrate statistics by day
- Trade count visualization
- Realized/unrealized PnL tracking
- Real-time PnL updates
- Funding rate PnL tracking

### Strategy Analysis
- Average Risk-Reward Ratio (RRR) calculation
- Profit/Loss ratio display
- Kelly criterion value
- Strategy health assessment
- Performance metrics and recommendations

### UI/UX Features
- Dark mode toggle
- Responsive design
- Real-time data updates via WebSockets
- Pagination for large datasets
- Interactive charts
- Automated data refresh

## Setup

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with necessary configuration:
```
COINGECKO_API_KEY=your_coingecko_api_key
DB_NAME=wallet_tracker
DB_USER=postgres
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432
```

## Database Setup

The application requires a PostgreSQL database with the following table:

```sql
CREATE TABLE favorite_addresses (
    id SERIAL PRIMARY KEY,
    address VARCHAR(255) NOT NULL,
    winrate NUMERIC,
    tag VARCHAR(255),
    top_coins JSON,
    top_profits JSON
);
```

## Usage

Run the server:
```bash
python app.py
```

Access the web interface at http://localhost:8080

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/user_state` | GET | Get account state and positions |
| `/api/trades_by_address` | GET | Get trade history for a specific address |
| `/api/pnl_timeseries` | GET | Get PnL time series data |
| `/api/favorite_address` | POST | Save a wallet address as favorite |
| `/api/favorite_addresses` | GET | Get all favorite addresses |
| `/api/track_pnl` | GET | Get real-time PnL data |
| `/api/coin_price_history` | GET | Get historical price data for a coin |

## Main Components

### Asset Positions and Account Summary
- Display account total value
- Withdrawable amount
- Total margin usage
- Total position value
- Current position details with entry prices, leverage, and PnL

### Trade History Query
- Query by time range
- Filter by coin
- Filter by trade size
- Multiple sort options
- Favorites management
- Merged trade view by hour

### PnL Analysis
- Cumulative PnL charts
- Winrate statistics
- Trade count statistics
- Real-time PnL tracking
- Realized/unrealized PnL breakdown
- 7-day, 30-day, and 90-day summaries

### Strategy Analysis
- Average RRR (Risk-Reward Ratio)
- P/L ratio calculation
- Kelly criterion value
- Strategy health assessment with ratings

### Price Charts
- Historical price charts
- Trade entry/exit points visualization
- Interactive tooltips
- Timeframe selection

## Technologies Used

- Backend: Python Flask with SocketIO
- Frontend: HTML/CSS/JavaScript with Tailwind CSS
- Database: PostgreSQL
- APIs: Hyperliquid WebSocket API, CoinGecko API
- Charts: Chart.js
- Real-time updates: WebSockets

## Notes

- Uses Hyperliquid's WebSocket API for real-time updates
- Automatic reconnection mechanism
- Data caching to avoid duplicate notifications
- Supports multiple cryptocurrency trading pairs
