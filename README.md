# Hyperliquid Wallet Tracker

這是一個用於追蹤 Hyperliquid 錢包交易的工具，提供即時和歷史交易數據分析。

## 功能特點

- 即時追蹤交易
- 資產倉位和賬戶摘要
- 交易歷史查詢
- 累計盈虧分析
- 實時盈虧追蹤
- 收藏地址管理
- 幣價歷史走勢圖
- 交易篩選和排序

## 設置

1. 創建虛擬環境（推薦）：
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

2. 安裝依賴：
```bash
pip install -r requirements.txt
```

3. 創建 `.env` 文件（可選）：
```bash
WALLET_ADDRESS=your_wallet_address_here
```

## 使用方法

運行服務器：
```bash
python app.py
```

訪問 http://localhost:5000 使用網頁界面。

## 主要功能說明

### 資產倉位和賬戶摘要
- 顯示賬戶總價值
- 可提現金額
- 總保證金使用量
- 總倉位價值
- 當前持倉詳情

### 交易歷史查詢
- 按時間範圍查詢
- 按幣種篩選
- 按交易大小篩選
- 多種排序方式
- 收藏常用地址

### 盈虧分析
- 累計盈虧圖表
- 勝率統計
- 交易數量統計
- 實時盈虧追蹤
- 已實現/未實現盈虧

### 其他功能
- 幣價歷史走勢圖
- 交易點位標記
- 自動更新數據
- 響應式設計

## 注意事項

- 使用 Hyperliquid 的 WebSocket API 進行即時更新
- 自動重連機制
- 數據緩存避免重複通知
- 支持多種加密貨幣交易對 