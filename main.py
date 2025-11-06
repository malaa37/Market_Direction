import ccxt
import pandas as pd
import numpy as np
import requests
import time
import os

# ==============================
# الإعدادات
# ==============================
SYMBOLS = ["BTC/USDT", "ETH/USDT"]
TIMEFRAMES = {"1H": "1h", "4H": "4h", "1D": "1d"}
CANDLES = 300
CHECK_INTERVAL_HOURS = 4  # يعيد التحليل كل 4 ساعات

# إعداد تليجرام (ضع القيم الخاصة بك)
TELEGRAM_ENABLED = True
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "PUT_YOUR_TOKEN_HERE")
CHAT_ID = os.getenv("CHAT_ID", "PUT_YOUR_CHAT_ID")

# ==============================
# دوال المؤشرات
# ==============================
def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(span=period, adjust=False).mean()
    ema_down = down.ewm(span=period, adjust=False).mean()
    rs = ema_up / (ema_down + 1e-9)
    return 100 - (100 / (1 + rs))

def macd(series, fast=12, slow=26, signal=9):
    fast_ema = ema(series, fast)
    slow_ema = ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line, macd_line - signal_line

def send_telegram(message):
    if not TELEGRAM_ENABLED:
        print(message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": message})

# ==============================
# تحليل الاتجاه لفريم واحد
# ==============================
def analyze_symbol(symbol, timeframe):
    exchange = ccxt.binance()
    df = pd.DataFrame(exchange.fetch_ohlcv(symbol, timeframe, limit=CANDLES),
                      columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
    df['close'] = df['close'].astype(float)

    # المتوسطات
    for ma in [20, 50, 100, 200]:
        df[f'ma{ma}'] = ema(df['close'], ma)

    # المؤشرات الأخرى
    df['rsi'] = rsi(df['close'])
    df['macd'], df['macd_signal'], df['macd_hist'] = macd(df['close'])

    # آخر القيم
    last = df.iloc[-1]
    price = last['close']
    ma20, ma50, ma100, ma200 = last['ma20'], last['ma50'], last['ma100'], last['ma200']
    rsi_now = last['rsi']
    macd_hist = last['macd_hist']

    # قواعد الاتجاه للفريم
    if price > ma200 and macd_hist > 0 and rsi_now > 50:
        direction = "📈 صاعد"
    elif price < ma200 and macd_hist < 0 and rsi_now < 50:
        direction = "📉 هابط"
    else:
        direction = "⚖️ متذبذب"

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "price": price,
        "direction": direction,
        "rsi": rsi_now,
        "macd": macd_hist,
        "ma": {"20": ma20, "50": ma50, "100": ma100, "200": ma200},
    }

# ==============================
# ترجيح الاتجاه من الفريمات الثلاثة
# ==============================
def overall_direction(directions):
    score = 0
    for d in directions:
        if "صاعد" in d:
            score += 1
        elif "هابط" in d:
            score -= 1

    if score >= 2:
        return "📈 الاتجاه العام: صاعد"
    elif score <= -2:
        return "📉 الاتجاه العام: هابط"
    else:
        return "⚖️ الاتجاه العام: متذبذب / ضعيف"

# ==============================
# تشغيل التحليل الكامل
# ==============================
previous_state = {}

def check_market():
    global previous_state
    exchange = ccxt.binance()
    full_message = "🚨 تحديث اتجاه السوق:\n\n"

    for sym in SYMBOLS:
        all_tf_results = []
        directions = []

        for label, tf in TIMEFRAMES.items():
            result = analyze_symbol(sym, tf)
            all_tf_results.append(f"{label}: {result['direction']}")
            directions.append(result['direction'])

        overall = overall_direction(directions)
        msg = f"{sym.replace('/USDT','')} ➜ {overall}\n" + "\n".join(all_tf_results)
        full_message += msg + "\n\n"

        # مقارنة بالتحليل السابق
        if sym not in previous_state or previous_state[sym] != overall:
            send_telegram(msg)
            previous_state[sym] = overall
            print(msg)
        else:
            print(f"{sym}: لا تغيير في الاتجاه العام ({overall})")

    print("✅ التحليل اكتمل.\n")

# ==============================
# التشغيل التلقائي
# ==============================
if __name__ == "__main__":
    print("🚀 بدأ تشغيل مراقبة السوق (BTC & ETH)...")
    while True:
        try:
            check_market()
        except Exception as e:
            print("❌ خطأ:", e)
        time.sleep(CHECK_INTERVAL_HOURS * 3600)
