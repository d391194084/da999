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
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        logging.info(f"開始抓取 {url}")
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = 'utf-8'
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.content, "html.parser")
        prices = {}
        
        # 抓取表格
        rows = soup.find_all("tr")
        for row in rows:
            tds = row.find_all("td")
            if len(tds) >= 2:
                name = tds[0].get_text(strip=True)
                # 過濾掉標題列
                if name in ["黃金", "白金", "白銀", "昨晚紐約收盤："] or "出/" in name:
                    continue
                
                if len(tds) == 3:
                    sell = tds[1].get_text(strip=True)
                    buy = tds[2].get_text(strip=True)
                    prices[name] = {"sell": sell, "buy": buy}
                else:
                    prices[name] = {"val": tds[1].get_text(strip=True)}
        return prices
    except Exception as e:
        logging.error(f"抓取失敗: {e}")
        return None

def send_telegram_message(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        logging.error("缺少 Telegram 變數設定")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload, timeout=10).raise_for_status()
        logging.info("Telegram 訊息已送出")
    except Exception as e:
        logging.error(f"發送失敗: {e}")

def main():
    # 取得台灣時間
    tw_now = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    
    # 讀取舊資料
    old_prices = {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                old_prices = json.load(f)
            except: old_prices = {}

    new_prices = fetch_prices()
    if not new_prices:
        return

    # 檢查是否變動
    changed = False
    msg_lines = [f"<b>📊 王鼎貴金屬價格更新</b>", f"⏰ {tw_now}", "━━━━━━━━━━━━━━━━"]

    for name, cur in new_prices.items():
        prev = old_prices.get(name)
        if prev != cur:
            changed = True
            tag = " 🔥" if old_prices else "" # 第一次執行不打火
            if "sell" in cur:
                msg_lines.append(f"• <b>{name}</b>{tag}\n  出: <code>{cur['sell']}</code> | 入: <code>{cur['buy']}</code>")
            else:
                msg_lines.append(f"• <b>{name}</b>{tag}\n  價格: <code>{cur['val']}</code>")

    if changed:
        # 發送 Telegram
        send_telegram_message("\n".join(msg_lines))
        
        # 存檔供下次比對
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(new_prices, f, ensure_ascii=False, indent=2)
        logging.info("偵測到變動，已更新並傳送通知")
    else:
        logging.info("價格無變動，跳過本次通知")

if __name__ == "__main__":
    main()
