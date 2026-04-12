import streamlit as st
import yfinance as yf
import pandas as pd
import time
import smtplib
from email.mime.text import MIMEText
import datetime

st.set_page_config(page_title="最強スキャナー GOD", layout="wide")
st.title("👑 最強スキャナー GOD（勝率 × RR）")

# =========================
# メール通知
# =========================
def send_mail(msg):
    sender = "あなたのgmail@gmail.com"
    password = "アプリパスワード"
    receiver = "あなたのgmail@gmail.com"

    message = MIMEText(msg)
    message["Subject"] = "📈 株アラート"
    message["From"] = sender
    message["To"] = receiver

    smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    smtp.login(sender, password)
    smtp.send_message(message)
    smtp.quit()

# =========================
# CSV
# =========================
df_codes = pd.read_csv("jpx400.csv", header=None)
codes = df_codes[0].astype(str).tolist()
name_dict = dict(zip(df_codes[0].astype(str), df_codes[1]))

# =========================
# セッション
# =========================
if "sent_alerts" not in st.session_state:
    st.session_state.sent_alerts = []

if "scan_results" not in st.session_state:
    st.session_state.scan_results = None

# =========================
# 日付リセット
# =========================
today = datetime.date.today()
if "last_reset" not in st.session_state:
    st.session_state.last_reset = today

if st.session_state.last_reset != today:
    st.session_state.sent_alerts = []
    st.session_state.last_reset = today

# =========================
# UI
# =========================
col1, col2, col3 = st.columns(3)

with col1:
    min_rsi = st.slider("RSI", 20, 60, 25)

with col2:
    min_vol = st.slider("出来高倍率", 1.0, 3.0, 1.3)

with col3:
    min_rr = st.slider("最低RR", 1.0, 3.0, 1.5)

top_n = st.selectbox("表示数", [5,10,20], index=0)

# =========================
# 自動制御（最重要）
# =========================
now = datetime.datetime.now()
hour = now.hour
minute = now.minute

manual_run = st.checkbox("🚀 手動ON", value=False)
time_run = (9 <= hour <= 10)

run_bot = manual_run or time_run

# 更新速度
if hour == 9 and minute < 5:
    refresh_sec = 60
elif 9 <= hour <= 10:
    refresh_sec = 300
else:
    refresh_sec = None

# =========================
# スキャン
# =========================
if run_bot:

    results = []
    progress = st.progress(0)

    for i, code in enumerate(codes):
        try:
            df = yf.Ticker(f"{code}.T").history(period="3mo")

            if len(df) < 50:
                continue

            df["MA20"] = df["Close"].rolling(20).mean()
            df["MA5"] = df["Close"].rolling(5).mean()

            delta = df["Close"].diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            rs = gain.rolling(14).mean() / loss.rolling(14).mean()
            df["RSI"] = 100 - (100 / (1 + rs))

            latest = df.iloc[-1]
            prev = df.iloc[-2]

            vol_ratio = df["Volume"].iloc[-1] / df["Volume"].rolling(20).mean().iloc[-1]

            if latest["Close"] < latest["MA20"] or latest["RSI"] < min_rsi or vol_ratio < min_vol:
                continue

            # ===== サイン =====
            signal = ""

            if latest["Close"] > latest["MA20"] and prev["Close"] < prev["MA20"]:
                signal = "🟢 押し目反転"

            elif latest["Close"] > df["High"].rolling(20).max().iloc[-2] and vol_ratio > 1.5:
                signal = "🔥 ブレイク"

            elif latest["Close"] > latest["MA5"] > latest["MA20"] and vol_ratio > 1.5:
                signal = "⚡ 初動"

            # ===== エントリー =====
            entry = None

            if signal == "🟢 押し目反転":
                entry = df["High"].iloc[-2]
            elif signal == "🔥 ブレイク":
                entry = df["High"].rolling(20).max().iloc[-2]
            elif signal == "⚡ 初動":
                entry = latest["MA5"]

            if not entry:
                continue

            # ===== RR計算 =====
            stop = entry * 0.97
            target = entry * 1.06

            risk = entry - stop
            reward = target - entry
            rr = reward / risk if risk > 0 else 0

            if rr < min_rr:
                continue

            score = rr * 100

            # ===== 通知 =====
            if rr >= 2.5 and "🔥" in signal:
                key = f"{code}_{signal}"

                if key not in st.session_state.sent_alerts:
                    msg = f"""
🔥 {code} {name_dict.get(code, "")}
{signal}
IN:{round(entry,1)}
RR:{round(rr,2)}
"""
                    send_mail(msg)
                    st.session_state.sent_alerts.append(key)

            results.append({
                "コード": code,
                "銘柄名": name_dict.get(code, ""),
                "株価": round(float(latest["Close"]),1),
                "サイン": signal,
                "RR": round(rr,2),
                "エントリー": round(entry,1),
                "損切り": round(stop,1),
                "利確": round(target,1),
                "スコア": round(score,1)
            })

        except:
            continue

        progress.progress((i+1)/len(codes))

    if results:
        st.session_state.scan_results = pd.DataFrame(results)\
            .sort_values("スコア", ascending=False)\
            .head(top_n)

# =========================
# 表示
# =========================
if st.session_state.scan_results is not None:
    st.subheader("🔥 上位銘柄")
    st.dataframe(st.session_state.scan_results, use_container_width=True)

# =========================
# 自動更新
# =========================
if run_bot and refresh_sec:
    time.sleep(refresh_sec)
    st.rerun()
