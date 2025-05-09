from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
import asyncio
import json
import websockets
from datetime import datetime, timedelta
import pandas as pd
from threading import Thread
from hyperliquid.info import Info
import psycopg2
import time

app = Flask(__name__)
socketio = SocketIO(app)

def get_db_connection():
    return psycopg2.connect(
        dbname='wallet_tracker',
        user='postgres',
        password='',
        host='localhost',
        port=5432
    )

# Hyperliquid WebSocket endpoint
WS_URL = "wss://api.hyperliquid.xyz/ws"

class TradeHistory:
    def __init__(self):
        self.trades = []
        self.known_trades = set()

    def add_trade(self, trade):
        trade_id = trade.get("id")
        if trade_id not in self.known_trades:
            self.known_trades.add(trade_id)
            self.trades.append(trade)
            # Sort trades by timestamp
            self.trades.sort(key=lambda x: x.get("time", 0), reverse=True)
            # Keep only last 1000 trades
            self.trades = self.trades[:1000]
            return True
        return False

trade_history = TradeHistory()

async def fetch_trade_history(wallet_address):
    async with websockets.connect(WS_URL) as websocket:
        # Subscribe to user events
        subscribe_message = {
            "method": "subscribe",
            "params": {
                "type": "user_events",
                "user": wallet_address
            }
        }
        
        await websocket.send(json.dumps(subscribe_message))
        print(f"Tracking wallet: {wallet_address}")
        
        while True:
            try:
                response = await websocket.recv()
                data = json.loads(response)
                
                if "data" in data and "fills" in data["data"]:
                    for fill in data["data"]["fills"]:
                        if trade_history.add_trade(fill):
                            # Emit new trade to connected clients
                            socketio.emit('new_trade', {
                                'timestamp': datetime.fromtimestamp(fill.get("time", 0) / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                                'coin': fill.get("coin", "Unknown"),
                                'side': fill.get("side", "Unknown"),
                                'size': fill.get("size", 0),
                                'price': fill.get("price", 0)
                            })
            except Exception as e:
                print(f"Error: {e}")
                break

def run_websocket(wallet_address):
    asyncio.run(fetch_trade_history(wallet_address))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/trades')
def get_trades():
    trades = []
    for trade in trade_history.trades:
        trades.append({
            'timestamp': datetime.fromtimestamp(trade.get("time", 0) / 1000).strftime('%Y-%m-%d %H:%M:%S'),
            'coin': trade.get("coin", "Unknown"),
            'side': trade.get("side", "Unknown"),
            'size': trade.get("size", 0),
            'price': trade.get("price", 0)
        })
    return jsonify(trades)

@app.route('/api/user_state')
def get_user_state():
    address = request.args.get('address')
    if not address:
        return jsonify({'error': 'No address provided'}), 400
    try:
        info = Info()
        user_data = info.user_state(address)
        return jsonify(user_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/trades_by_address')
def get_trades_by_address():
    address = request.args.get('address')
    page = int(request.args.get('page', 1))
    limit = 20
    start_time = request.args.get('start_time', type=int)
    end_time = request.args.get('end_time', type=int)
    if not address:
        return jsonify({'error': 'No address provided'}), 400
    try:
        info = Info()
        if start_time:
            fills = info.user_fills_by_time(address, start_time, end_time)
        else:
            fills = info.user_fills(address)
        # Sort by time descending
        fills = sorted(fills, key=lambda x: x.get('time', 0), reverse=True)
        start = (page - 1) * limit
        end = start + limit
        paged_fills = fills[start:end]
        trades = []
        for fill in paged_fills:
            trades.append({
                'timestamp': datetime.fromtimestamp(fill.get("time", 0) / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                'coin': fill.get("coin", "Unknown"),
                'side': fill.get("side", "Unknown"),
                'sz': fill.get("sz", 0),
                'px': fill.get("px", 0),
                'dir': fill.get("dir", ""),
                'closedPnl': fill.get("closedPnl", 0),
                'hash': fill.get("hash", ""),
                'oid': fill.get("oid", ""),
                'crossed': fill.get("crossed", False),
                'fee': fill.get("fee", 0),
                'tid': fill.get("tid", ""),
                'feeToken': fill.get("feeToken", "")
            })
        return jsonify({
            'trades': trades,
            'total': len(fills),
            'page': page,
            'pages': (len(fills) + limit - 1) // limit
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/pnl_timeseries')
def pnl_timeseries():
    address = request.args.get('address')
    try:
        info = Info()
        fills = info.user_fills(address)
        if not fills:
            return jsonify([])
        now = datetime.now()
        df = pd.DataFrame(fills)
        df['date'] = df['time'].apply(lambda t: datetime.fromtimestamp(t / 1000).strftime('%Y-%m-%d'))
        df['closedPnl'] = df['closedPnl'].astype(float)
        df['sz'] = df['sz'].astype(float)
        df['px'] = df['px'].astype(float)
        df['size_usd'] = df['sz'] * df['px']
        df['dt'] = df['time'].apply(lambda t: datetime.utcfromtimestamp(t / 1000))
        
        # 计算总体胜率
        total_trades = len(df)
        winning_trades = len(df[df['closedPnl'] > 0])
        overall_winrate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # 计算累计盈亏
        total_pnl = df['closedPnl'].sum()
        
        # Calculate cumulative PnL for 7D, 30D, 90D
        cutoff_7d = now - timedelta(days=7)
        cutoff_30d = now - timedelta(days=30)
        cutoff_90d = now - timedelta(days=90)
        cum_pnl_7d = df[df['dt'] >= cutoff_7d]['closedPnl'].sum()
        cum_pnl_30d = df[df['dt'] >= cutoff_30d]['closedPnl'].sum()
        cum_pnl_90d = df[df['dt'] >= cutoff_90d]['closedPnl'].sum()
        
        # Group by date
        summary = []
        for date, group in df.groupby('date'):
            num_trades = len(group)
            winrate = 100.0 * (group['closedPnl'] > 0).sum() / num_trades if num_trades > 0 else 0.0
            coins_traded = sorted(group['coin'].unique())
            median_size_usd = float(group['size_usd'].median()) if num_trades > 0 else 0.0
            summary.append({
                'date': date,
                'num_trades': num_trades,
                'winrate': round(winrate, 2),
                'coins_traded': coins_traded,
                'median_size_usd': median_size_usd,
                'cum_pnl_7d': cum_pnl_7d,
                'cum_pnl_30d': cum_pnl_30d,
                'cum_pnl_90d': cum_pnl_90d
            })
            
        return jsonify({
            'daily_summary': summary,
            'overall_stats': {
                'total_pnl': total_pnl,
                'overall_winrate': round(overall_winrate, 2),
                'total_trades': total_trades,
                'winning_trades': winning_trades
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/favorite_address', methods=['POST'])
def add_favorite_address():
    data = request.json
    address = data['address']
    winrate = data['winrate']
    tag = data['tag']
    top_coins = json.dumps(data['top_coins'])
    top_profits = json.dumps(data['top_profits'])
    dbconn = get_db_connection()
    c = dbconn.cursor()
    c.execute('INSERT INTO favorite_addresses (address, winrate, tag, top_coins, top_profits) VALUES (%s, %s, %s, %s, %s)',
              (address, winrate, tag, top_coins, top_profits))
    dbconn.commit()
    c.close()
    dbconn.close()
    return jsonify({'success': True})

@app.route('/api/favorite_addresses')
def get_favorite_addresses():
    dbconn = get_db_connection()
    c = dbconn.cursor()
    c.execute('SELECT address, tag FROM favorite_addresses ORDER BY tag')
    rows = c.fetchall()
    c.close()
    dbconn.close()
    # rows: [(address, tag), ...]
    result = [{'address': r[0], 'tag': r[1]} for r in rows]
    return jsonify(result)

def get_realized_pnl_from_trades(info, address, start_time=None, end_time=None):
    if start_time and end_time:
        fills = info.user_fills_by_time(address, start_time, end_time)
    else:
        fills = info.user_fills(address)
    
    total_realized_pnl = 0.0
    for fill in fills:
        if "closedPnl" in fill:
            total_realized_pnl += float(fill["closedPnl"])
    
    return total_realized_pnl

def get_funding_pnl(info, address, start_time, end_time=None):
    funding_history = info.user_funding_history(address, start_time, end_time)
    
    total_funding_pnl = 0.0
    for record in funding_history:
        if "delta" in record and "usdc" in record["delta"]:
            total_funding_pnl += float(record["delta"]["usdc"])
    
    return total_funding_pnl

def get_unrealized_pnl(info, address):
    user_state = info.user_state(address)
    
    total_unrealized_pnl = 0.0
    for position_data in user_state["assetPositions"]:
        position = position_data["position"]
        if "unrealizedPnl" in position:
            total_unrealized_pnl += float(position["unrealizedPnl"])
    
    return total_unrealized_pnl

def get_total_cumulative_pnl(info, address, start_time=None, end_time=None):
    realized_pnl = get_realized_pnl_from_trades(info, address, start_time, end_time)
    
    funding_pnl = 0.0
    if start_time:
        funding_pnl = get_funding_pnl(info, address, start_time, end_time)
    
    unrealized_pnl = get_unrealized_pnl(info, address)
    
    total_pnl = realized_pnl + funding_pnl + unrealized_pnl
    
    return {
        "realized_pnl": realized_pnl,
        "funding_pnl": funding_pnl,
        "unrealized_pnl": unrealized_pnl,
        "total_cumulative_pnl": total_pnl
    }

@app.route('/api/track_pnl')
def track_pnl():
    address = request.args.get('address')
    if not address:
        return jsonify({'error': 'No address provided'}), 400
    
    try:
        info = Info()
        end_time = int(time.time() * 1000)
        start_time = end_time - (30 * 24 * 60 * 60 * 1000)  # 30 days ago
        
        pnl_data = get_total_cumulative_pnl(info, address, start_time, end_time)
        return jsonify(pnl_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    wallet_address = "0xd5f7974e1be5b336094a18c230f39607934e367d"
    
    # Start WebSocket connection in a separate thread
    websocket_thread = Thread(target=run_websocket, args=(wallet_address,))
    websocket_thread.daemon = True
    websocket_thread.start()
    
    # Run Flask app
    socketio.run(app, debug=True, host='127.0.0.1', port=8080) 