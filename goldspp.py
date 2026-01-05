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
        
        rows = soup.find_all("tr")
        for row in rows:
            # 去除隱形空白字元與前後空格
            tds = [td.get_text(strip=True).replace('\xa0', ' ') for td in row.find_all("td")]
            
            if len(tds) < 2:
                continue
            
            name = tds[0]
            
            # 過濾掉表格內部的標題/說明文字
            if "出 / 入" in name or "出 / 每" in name or name == "品名":
                continue
            
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
        logging.error("錯誤: 缺少 Telegram 環境變數設定")
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
        logging.info("Telegram 訊息已送出")
    except Exception as e:
        logging.error(f"Telegram 發送失敗: {e}")

def main():
    tw_now = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    
    # 1. 讀取舊資料
    old_prices = {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                old_prices = json.load(f)
            except: 
                old_prices = {}

    # 2. 抓取新資料
    new_prices = fetch_prices()
    if not new_prices:
        return

    # 3. 準備變量
    msg_lines = [f"<b>📊 王鼎貴金屬價格更新</b>", f"⏰ {tw_now}", "━━━━━━━━━━━━━━━━"]
    category_icons = {"黃金": "🟡", "白金": "⚪️", "白銀": "🥈", "昨晚紐約收盤：": "🌎"}
    
    has_any_change = False  # 用來記錄是否有任何一項發生變動

    # 4. 比對與排版
    for name, cur in new_prices.items():
        prev = old_prices.get(name)
        
        # 判定變動邏輯：
        # 如果舊資料不存在，視為第一次執行 (不標火)
        # 如果舊資料存在且與新資料不同，則視為變動 (標火)
        is_changed = bool(old_prices) and (prev != cur)
        
        if is_changed:
            has_any_change = True # 只要有一項變動，就設為 True
            
        tag = " 🔥" if is_changed else ""

        # 分類標題處理
        if "sell" in cur and (("出" in cur['sell']) or not cur['sell']):
            icon = category_icons.get(name, "📌")
            msg_lines.append(f"\n{icon} <b><u>{name}</u></b>")
            continue
        
        # 一般商品處理
        if "sell" in cur:
            msg_lines.append(f"• <b>{name}</b>{tag}\n  出: <code>{cur['sell']}</code> | 入: <code>{cur['buy']}</code>")
        else:
            msg_lines.append(f"• <b>{name}</b>{tag}\n  價格: <code>{cur.get('val', '--')}</code>")

    # 5. 判斷是否發送
    # 如果是第一次執行 (old_prices 為空)，或者偵測到變動 (has_any_change 為 True) 則發送
    if not old_prices or has_any_change:
        send_telegram_message("\n".join(msg_lines))
        # 發送後存檔，供下次比對
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(new_prices, f, ensure_ascii=False, indent=2)
        logging.info("偵測到變動或首次運行，訊息已發送並更新存檔。")
    else:
        logging.info("價格無變動，跳過本次發送。")

if __name__ == "__main__":
    main()
