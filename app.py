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
import requests
from collections import defaultdict
import os
from dotenv import load_dotenv

# 加載環境變量
load_dotenv()

app = Flask(__name__)
socketio = SocketIO(app)

# 從環境變量讀取配置
COINGECKO_API_KEY = os.getenv('COINGECKO_API_KEY')
DB_NAME = os.getenv('DB_NAME', 'wallet_tracker')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')

def get_db_connection():
    return psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
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
        # 合併：coin, dir, 小時
        merged = defaultdict(lambda: {'sz': 0, 'closedPnl': 0, 'px_sum': 0, 'px_weight': 0, 'count': 0, 'first_time': None, 'last_time': None})
        for fill in fills:
            coin = fill.get('coin', 'Unknown')
            dir_ = fill.get('dir', '')
            t = fill.get('time', 0)
            # 向下取整到小時
            hour_ts = t - (t % (60*60*1000))
            key = (coin, dir_, hour_ts)
            sz = float(fill.get('sz', 0))
            px = float(fill.get('px', 0))
            closedPnl = float(fill.get('closedPnl', 0))
            merged[key]['sz'] += sz
            merged[key]['closedPnl'] += closedPnl
            merged[key]['px_sum'] += px * abs(sz)
            merged[key]['px_weight'] += abs(sz)
            merged[key]['count'] += 1
            if merged[key]['first_time'] is None or t < merged[key]['first_time']:
                merged[key]['first_time'] = t
            if merged[key]['last_time'] is None or t > merged[key]['last_time']:
                merged[key]['last_time'] = t
        # 轉成列表
        merged_list = []
        for (coin, dir_, hour_ts), v in merged.items():
            px = v['px_sum'] / v['px_weight'] if v['px_weight'] else 0
            merged_list.append({
                'timestamp': datetime.fromtimestamp(hour_ts / 1000).strftime('%Y-%m-%d %H:00:00'),
                'coin': coin,
                'action': dir_,
                'sz': v['sz'],
                'px': px,
                'closedPnl': v['closedPnl'],
                'count': v['count'],
                'last_time': v['last_time']
            })
        # 用 last_time 倒序排序
        merged_list = sorted(merged_list, key=lambda x: x['last_time'], reverse=True)
        total = len(merged_list)
        start = (page - 1) * limit
        end = start + limit
        paged = merged_list[start:end]
        return jsonify({
            'trades': paged,
            'total': total,
            'page': page,
            'pages': (total + limit - 1) // limit
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
        
        # 添加新的列
        df['fee_usd'] = df['fee'].astype(float)
        df['px'] = df['px'].astype(float)
        df['sz'] = df['sz'].astype(float)
        df['closedPnl'] = df['closedPnl'].astype(float)
        df['startPosition'] = df['startPosition'].astype(float)
        
        # 按訂單ID分組計算
        order_groups = df.groupby('oid')
        
        # 計算每個訂單的總成交量和加權平均價格
        order_summary = order_groups.agg({
            'sz': 'sum',
            'px': lambda x: (x * df.loc[x.index, 'sz']).sum() / df.loc[x.index, 'sz'].sum(),
            'closedPnl': 'sum',
            'fee_usd': 'sum',
            'time': 'first',
            'coin': 'first',
            'dir': 'first',
            'hash': 'first'
        }).reset_index()
        
        # 計算淨盈虧
        order_summary['netPnl'] = order_summary['closedPnl'] - order_summary['fee_usd']
        print(order_summary[['oid','coin','closedPnl','fee_usd','netPnl']].head())
        
        # 計算 RRR (Risk-Reward Ratio)
        # 假設每筆交易的止損點是進場價格的 2%
        order_summary['entry_price'] = order_summary['px']
        order_summary['stop_loss'] = order_summary['entry_price'] * 0.98  # 2% 止損
        order_summary['take_profit'] = order_summary['entry_price'] * (1 + order_summary['netPnl'] / (order_summary['sz'] * order_summary['entry_price']))
        order_summary['rrr'] = abs((order_summary['take_profit'] - order_summary['entry_price']) / (order_summary['entry_price'] - order_summary['stop_loss']))
        
        # 計算 P/L Ratio
        avg_profit = order_summary[order_summary['netPnl'] > 0]['netPnl'].mean()
        avg_loss = abs(order_summary[order_summary['netPnl'] < 0]['netPnl'].mean())
        pl_ratio = avg_profit / avg_loss if avg_loss > 0 else None
        
        # 計算 Kelly 公式
        winrate_decimal = len(order_summary[order_summary['netPnl'] > 0]) / len(order_summary) if len(order_summary) > 0 else 0
        kelly = winrate_decimal - (1 - winrate_decimal) / pl_ratio if pl_ratio else None
        
        # 獲取當前市價並轉換為float
        mark_prices = info.all_mids()
        mark_prices = {k: float(v) for k, v in mark_prices.items()}
        
        # 計算未實現盈虧
        # 注意：這裡需要從 user_state 獲取當前持倉信息
        user_state = info.user_state(address)
        unrealized_pnl = 0.0
        
        for position in user_state.get('assetPositions', []):
            coin = position.get('coin')
            if coin in mark_prices:
                position_data = position.get('position', {})
                size = float(position_data.get('sz', 0))
                entry_price = float(position_data.get('entryPx', 0))
                leverage = float(position_data.get('leverage', 1))
                
                if size != 0 and entry_price != 0:
                    mark_price = mark_prices[coin]
                    unrealized_pnl += (mark_price - entry_price) * size * leverage
        
        # 更新DataFrame
        df = order_summary.copy()
        df['date'] = df['time'].apply(lambda t: datetime.utcfromtimestamp(t / 1000).strftime('%Y-%m-%d'))
        df['dt'] = df['time'].apply(lambda t: datetime.utcfromtimestamp(t / 1000))
        df['size_usd'] = df['sz'] * df['px']
        
        # 使用 netPnl 計算勝率
        total_trades = len(df)
        winning_trades = len(df[df['netPnl'] > 0])
        overall_winrate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # 計算累計淨盈虧（包括未實現盈虧）
        total_pnl = df['netPnl'].sum() + unrealized_pnl
        
        # Calculate cumulative PnL for 7D, 30D, 90D
        cutoff_7d = now - timedelta(days=7)
        cutoff_30d = now - timedelta(days=30)
        cutoff_90d = now - timedelta(days=90)
        cum_pnl_7d = df[df['dt'] >= cutoff_7d]['netPnl'].sum()
        cum_pnl_30d = df[df['dt'] >= cutoff_30d]['netPnl'].sum()
        cum_pnl_90d = df[df['dt'] >= cutoff_90d]['netPnl'].sum()
        
        # Group by date
        summary = []
        for date, group in df.groupby('date'):
            num_trades = len(group)
            winrate = 100.0 * (group['netPnl'] > 0).sum() / num_trades if num_trades > 0 else 0.0
            coins_traded = sorted(group['coin'].unique())
            median_size_usd = float(group['size_usd'].median()) if num_trades > 0 else 0.0

            # for debug purposes 
            print(f"=== {date} trades netPnls: ===")
            print(group['netPnl'].tolist())

            summary.append({
                'date': date,
                'num_trades': num_trades,
                'winrate': round(winrate, 2),
                'coins_traded': coins_traded,
                'median_size_usd': median_size_usd,
                'sum_netPnl': round(group['netPnl'].sum(), 2),
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
                'winning_trades': winning_trades,
                'avg_rrr': round(order_summary['rrr'].mean(), 2),
                'pl_ratio': round(pl_ratio, 2) if pl_ratio else None,
                'kelly': round(kelly * 100, 2) if kelly else None
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

@app.route('/api/coin_price_history')
def coin_price_history():
    coin_id = request.args.get('coin_id')
    from_ts = request.args.get('from')
    to_ts = request.args.get('to')
    if not coin_id or not from_ts or not to_ts:
        return jsonify({'error': '缺少參數'}), 400

    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"
    headers = {
        "x-cg-demo-api-key": COINGECKO_API_KEY
    }
    params = {
        "vs_currency": "usd",
        "from": from_ts,
        "to": to_ts
    }
    resp = requests.get(url, headers=headers, params=params)
    return jsonify(resp.json())

if __name__ == '__main__':
    wallet_address = "0xd5f7974e1be5b336094a18c230f39607934e367d"
    
    # Start WebSocket connection in a separate thread
    websocket_thread = Thread(target=run_websocket, args=(wallet_address,))
    websocket_thread.daemon = True
    websocket_thread.start()
    
    # Run Flask app
    socketio.run(app, debug=True, host='127.0.0.1', port=8080) 