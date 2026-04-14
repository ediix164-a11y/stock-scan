import streamlit as st
import yfinance as yf
import pandas as pd
import time
import smtplib
from email.mime.text import MIMEText
import datetime

# =========================
# 基本設定
# =========================
st.set_page_config(page_title="寄付き特化BOT", layout="wide")
st.title("🚀 寄付き5分スキャナー（超高速モード）")

# =========================
# メール通知
# =========================
def send_mail(msg):
    sender = "ediix.164@gmail.com"
    password = "srhg uzgk lccr yssk"
    receiver = "ediix.164@gmail.com"

    message = MIMEText(msg)
    message["Subject"] = "🚀 寄付きアラート"
    message["From"] = sender
    message["To"] = receiver

    smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    smtp.login(sender, password)
    smtp.send_message(message)
    smtp.quit()

# =========================
# CSV読み込み（安全版）
# =========================
df_raw = pd.read_csv("jpx400.csv")

valid_codes = pd.to_numeric(df_raw.iloc[:, 0], errors='coerce')
df = df_raw[valid_codes.notna()]

codes = df.iloc[:, 0].astype(int).astype(str).tolist()
name_dict = dict(zip(codes, df.iloc[:, 1]))

# =========================
# セッション
# =========================
if "alerts" not in st.session_state:
    st.session_state.alerts = []

# =========================
# 時間制御（寄付き専用）
# =========================
now = datetime.datetime.now()
hour = now.hour
minute = now.minute

manual = st.checkbox("手動ON（テスト用）", value=False)

# 9:00〜9:05のみ稼働
run_bot = manual or (hour == 9 and minute <= 5)

# 1分更新
refresh_sec = 60 if run_bot else None

st.write(f"現在時刻: {hour}:{minute}")
st.write(f"稼働状態: {'ON' if run_bot else 'OFF'}")

# =========================
# スキャン
# =========================
if run_bot:

    results = []
    progress = st.progress(0)

    for i, code in enumerate(codes):
        try:
            df = yf.Ticker(f"{code}.T").history(period="5d", interval="1m")

            if len(df) < 50:
                continue

            # 前日終値
            prev_close = yf.Ticker(f"{code}.T").history(period="2d")["Close"].iloc[-2]

            latest = df.iloc[-1]

            # ===== ギャップ判定 =====
            gap = (latest["Open"] - prev_close) / prev_close

            if gap < 0.02:
                continue  # 2%以上ギャップのみ

            # ===== 出来高急増 =====
            vol_ma = df["Volume"].rolling(20).mean().iloc[-1]
            if vol_ma == 0:
                continue

            vol_ratio = latest["Volume"] / vol_ma

            if vol_ratio < 2.0:
                continue

            # ===== 高値ブレイク =====
            high_5 = df["High"].rolling(5).max().iloc[-2]

            if latest["Close"] <= high_5:
                continue

            # ===== エントリー =====
            entry = latest["Close"]
            stop = latest["Low"]
            risk = entry - stop

            if risk <= 0:
                continue

            # ボラ除外
            if (risk / entry) > 0.03:
                continue

            target = entry + (risk * 2.0)
            rr = (target - entry) / risk

            if rr < 2:
                continue

            # ===== 通知 =====
            key = f"{code}"

            if key not in st.session_state.alerts:
                msg = f"""
🚀 {code} {name_dict.get(code,"")}
寄付きブレイク
価格:{round(entry,1)}
損切:{round(stop,1)}
RR:{round(rr,2)}
"""
                send_mail(msg)
                st.session_state.alerts.append(key)

            results.append({
                "コード": code,
                "銘柄名": name_dict.get(code, ""),
                "価格": round(entry,1),
                "ギャップ%": round(gap*100,1),
                "出来高倍率": round(vol_ratio,1),
                "RR": round(rr,2)
            })

        except:
            continue

        progress.progress((i+1)/len(codes))

    if results:
        df_res = pd.DataFrame(results).sort_values("RR", ascending=False)
        st.dataframe(df_res, width="stretch")

        st.subheader("📊 TradingView")
        for i, row in df_res.iterrows():
            st.link_button(
                f"{row['コード']} {row['銘柄名']}",
                f"https://jp.tradingview.com/symbols/TSE-{row['コード']}/"
            )

# =========================
# 自動更新
# =========================
if run_bot and refresh_sec:
    time.sleep(refresh_sec)
    st.rerun()
