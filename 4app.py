import streamlit as st
import yfinance as yf
import pandas as pd
import time
import smtplib
from email.mime.text import MIMEText
import os
import datetime

st.set_page_config(page_title="最強スキャナー GOD", layout="wide")

st.title("👑 最強スキャナー GOD（勝率 × RR）")

# =========================
# メール通知関数
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
# セッション初期化
# =========================
if "sent_alerts" not in st.session_state:
    st.session_state.sent_alerts = []

if "scan_results" not in st.session_state:
    st.session_state.scan_results = None

if "selected_code" not in st.session_state:
    st.session_state.selected_code = None

if "trade_log" not in st.session_state:
    st.session_state.trade_log = []

# =========================
# 1日1回リセット（重要）
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
col1, col2, col3, col4 = st.columns(4)

with col1:
    min_rsi = st.slider("RSI", 20, 60, 25)

with col2:
    min_vol = st.slider("出来高倍率", 1.0, 3.0, 1.3)

with col3:
    min_rr = st.slider("最低RR", 1.0, 3.0, 1.5)

with col4:
    top_n = st.selectbox("表示数", [5,10,20], index=0)

auto_refresh = st.checkbox("🔄 自動更新", value=True)

# =========================
# 勝率計算
# =========================
win_rate_dict = {}

if st.session_state.trade_log:
    df_log = pd.DataFrame(st.session_state.trade_log)
    summary = df_log.groupby("サイン")["結果"].apply(
        lambda x: (x == "勝ち").mean()
    )
    win_rate_dict = summary.to_dict()

# =========================
# スキャン（完全自動）
# =========================
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

        # ===== 損切り・利確 =====
        stop = entry * 0.97
        target = entry * 1.06

        risk = entry - stop
        reward = target - entry
        rr = reward / risk if risk > 0 else 0

        # ===== 勝率 =====
        win_rate = win_rate_dict.get(signal, 0.5)

        # ===== フィルター =====
        if rr < min_rr or win_rate < 0.5:
            continue

        score = rr * 100 + win_rate * 100

        # ===== メール通知（重複防止）=====
        if rr >= 2.1 and "🔥" in signal:
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
            "勝率": round(win_rate*100,1),
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

    st.subheader("🔥 勝てる銘柄だけ")
    st.dataframe(st.session_state.scan_results, use_container_width=True)

    for i, row in st.session_state.scan_results.iterrows():
        if st.button(f"{row['コード']} {row['銘柄名']}", key=f"btn_{i}"):
            st.session_state.selected_code = row["コード"]

# =========================
# チャート
# =========================
if st.session_state.selected_code:
    code = st.session_state.selected_code
    st.link_button("📊 チャート", f"https://jp.tradingview.com/symbols/TSE-{code}/")

# =========================
# 自動更新
# =========================
if auto_refresh:
    time.sleep(300)
    st.rerun()
