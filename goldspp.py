import os
import re
import requests
from bs4 import BeautifulSoup

TG_TOKEN = os.environ["TG_TOKEN"]       # GitHub Actions Secret
CHAT_ID = "8272362300"
PRICE_URL = "https://wdpm.com.tw"         # 首頁含你截圖那塊 [web:32]

def fetch_prices():
    resp = requests.get(PRICE_URL, timeout=10)
    resp.raise_for_status()
    html = resp.text

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    # 日期與昨日紐約收盤
    date_m = re.search(r"(\d+ 年 \d+月 \d+日)", text)
    date_str = date_m.group(1) if date_m else "今日報價"

    ny_m = re.search(r"昨日紐約收盤：\s*USD\s*([\d.]+)\s*/\s*盎司", text)
    ny_close = ny_m.group(1) if ny_m else "N/A"

    def row(name):
        m = re.search(name + r"\s*(\d+)\s*(\d+)", text)
        if m:
            return m.group(1), m.group(2)
        return "N/A", "N/A"

    g1_out, g1_in = row("1公斤裝王鼎進口條塊")
    g5_out, g5_in = row("王鼎5台兩條塊")
    g1t_out, g1t_in = row("王鼎壹台兩金龍條")

    lines = [
        f"{date_str}",
        f"昨日紐約收盤: USD {ny_close} / 盎司",
        f"1公斤裝王鼎進口條塊 出 {g1_out} 入 {g1_in}",
        f"王鼎5台兩條塊 出 {g5_out} 入 {g5_in}",
        f"王鼎壹台兩金龍條 出 {g1t_out} 入 {g1t_in}",
    ]
    return "\n".join(lines)

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    resp = requests.post(url, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()

def main():
    msg = fetch_prices()
    print(msg)
    res = send_telegram(msg)
    print(res)

if __name__ == "__main__":
    main()

