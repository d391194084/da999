import requests
from bs4 import BeautifulSoup
import json
import os
import logging
from datetime import datetime, timedelta

# 配置檔案名稱
DATA_FILE = "last_price.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def fetch_prices():
    url = "https://wdpm.com.tw/price/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        logging.info(f"開始從 {url} 抓取最新價格...")
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = 'utf-8'
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.content, "html.parser")
        prices = {}
        
        # 抓取表格中所有的行 (tr)
        rows = soup.find_all("tr")
        for row in rows:
            tds = [td.get_text(strip=True) for td in row.find_all("td")]
            
            # 跳過空行或欄位不足的行
            if len(tds) < 2:
                continue
            
            name = tds[0]
            
            # 過濾掉表格內部的說明文字列，避免混淆
            if "出 / 入" in name or "出 / 每" in name or name == "品名":
                continue
            
            # 判斷是三欄格式 (買賣價) 還是兩欄格式 (單一價值)
            if len(tds) >= 3:
                prices[name] = {"sell": tds[1], "buy": tds[2]}
            else:
                prices[name] = {"val": tds[1]}
                
        return prices
    except Exception as e:
        logging.error(f"網頁抓取失敗: {e}")
        return None

def send_telegram_message(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logging.error("錯誤: 找不到 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID 環境變數")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id, 
        "text": text, 
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, data=payload, timeout=10).raise_for_status()
        logging.info("Telegram 訊息已成功送出")
    except Exception as e:
        logging.error(f"Telegram 發送失敗: {e}")

def main():
    # 取得台灣時間 (UTC+8)
    tw_now = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    
    # 1. 讀取舊資料用於比對
    old_prices = {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                old_prices = json.load(f)
            except: 
                old_prices = {}

    # 2. 抓取最新資料
    new_prices = fetch_prices()
    if not new_prices:
        return

    # 3. 建立訊息內容
    msg_lines = [
        f"<b>📊 王鼎貴金屬價格更新</b>",
        f"⏰ {tw_now}",
        "━━━━━━━━━━━━━━━━"
    ]

    # 定義大分類的圖示
    category_icons = {
        "黃金": "🟡",
        "白金": "⚪️",
        "白銀": "🥈",
        "昨晚紐約收盤：": "🌎"
    }

    for name, cur in new_prices.items():
        prev = old_prices.get(name)
        # 判斷是否變動 (且確保不是第一次執行)
        is_changed = bool(old_prices) and (prev != cur)
        tag = " 🔥" if is_changed else ""

        # A. 處理大分類標題 (判斷特徵：sell 欄位包含 "出" 字眼或為空)
        if "sell" in cur and (("出" in cur['sell']) or not cur['sell']):
            icon = category_icons.get(name, "📌")
            msg_lines.append(f"\n{icon} <u><b>{name}</b></u>")
            continue
        
        # B. 處理一般價格項目
        if "sell" in cur:
            # 買賣報價格式
            sell_val = cur['sell'] if cur['sell'] else "--"
            buy_val = cur['buy'] if cur['buy'] else "--"
            msg_lines.append(f"• <b>{name}</b>{tag}\n  出: <code>{sell_val}</code> | 入: <code>{buy_val}</code>")
        else:
            # 單一數值格式 (如：收盤價)
            val = cur.get('val', '--')
            icon = category_icons.get(name, "•")
            msg_lines.append(f"{icon} <b>{name}</b>{tag}\n  價格: <code>{val}</code>")

    # 4. 發送訊息 (不論有無變動都會發送)
    send_telegram_message("\n".join(msg_lines))
    
    # 5. 更新本地 JSON 資料庫，供下次比對
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(new_prices, f, ensure_ascii=False, indent=2)
    
    logging.info("流程執行完畢")

if __name__ == "__main__":
    main()
