from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
import os
import json
import logging
from pathlib import Path

STATE_FILE = Path("state.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def load_last_state():
    if STATE_FILE.exists():
        try:
            with STATE_FILE.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.warning(f"讀取 state 失敗: {e}")
    return {}

def save_state(state: dict):
    try:
        with STATE_FILE.open("w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        logging.info("已更新 state.json")
    except Exception as e:
        logging.error(f"寫入 state 失敗: {e}")

def scrape_gold_price():
    url = "https://wdpm.com.tw"
    try:
        logging.info(f"開始抓取 {url}")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"HTTP 連線失敗: {e}")
        return None, None

    soup = BeautifulSoup(resp.content, "html.parser")
    tables = soup.find_all("table")
    if not tables:
        logging.warning("找不到任何 table，可能頁面結構變更")
        return None, None

    prices = {}
    lines = []
    lines.append("<b>📊 王鼎貴金屬價格更新</b>")
    taipei_now = datetime.now(ZoneInfo("Asia/Taipei"))
    lines.append(f"⏰ {taipei_now.strftime('%Y-%m-%d %H:%M')}")
    lines.append("━━━━━━━━━━━━━━━━")

    for table in tables:
        for row in table.find_all("tr"):
            tds = row.find_all("td")
            if len(tds) == 3:
                name = tds[0].get_text(strip=True)
                sell = tds[1].get_text(strip=True)
                buy = tds[2].get_text(strip=True)
                if not name or "出" in name or "入" in name:
                    continue
                key = name
                prices[key] = {"sell": sell, "buy": buy}

    if not prices:
        logging.warning("解析不到任何價格資料")
        return None, None

    return prices, "\n".join(lines)

def build_changed_message(old: dict, new: dict, header: str):
    changed_lines = [header, ""]
    changed = False

    for name, cur in new.items():
        prev = old.get(name)
        if prev != cur:
            changed = True
            if prev:
                changed_lines.append(
                    f"• <b>{name}</b>\n"
                    f"  出: <code>{prev['sell']}</code> ➜ <code>{cur['sell']}</code>\n"
                    f"  入: <code>{prev['buy']}</code> ➜ <code>{cur['buy']}</code>"
                )
            else:
                changed_lines.append(
                    f"• <b>{name}</b>\n"
                    f"  出: <code>{cur['sell']}</code>\n"
                    f"  入: <code>{cur['buy']}</code>"
                )

    if not changed:
        return None
    return "\n".join(changed_lines)

def send_telegram_message(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logging.error("缺少 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        resp = requests.post(url, data=payload, timeout=10)
        resp.raise_for_status()
        logging.info("Telegram 訊息已送出")
    except requests.exceptions.RequestException as e:
        logging.error(f"發送 Telegram 失敗: {e}")

def main():
    last_state = load_last_state()
    new_prices, header = scrape_gold_price()
    if new_prices is None:
        raise SystemExit("抓取失敗")

    msg = build_changed_message(
        last_state.get("prices", {}),
        new_prices,
        header
    )

    if msg:
        send_telegram_message(msg)
        last_state["prices"] = new_prices
        taipei_now = datetime.now(ZoneInfo("Asia/Taipei"))
        last_state["last_sent_at"] = taipei_now.isoformat()
        save_state(last_state)
    else:
        logging.info("價格無變動，本次不發送通知")

if __name__ == "__main__":
    main()


