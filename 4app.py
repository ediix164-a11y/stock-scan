import streamlit as st
import yfinance as yf
import pandas as pd
import time
import smtplib
from email.mime.text import MIMEText
import datetime
import pytz

# =========================
# 基本設定
# =========================
st.set_page_config(page_title="寄付き特化BOT", layout="wide")
st.title("🚀 寄付き5分スキャナー（完全版）")

# =========================
# 日本時間
# =========================
jst = pytz.timezone('Asia/Tokyo')
now = datetime.datetime.now(jst)

hour = now.hour
minute = now.minute

st.write("現在時刻（JST）:", now.strftime("%Y-%m-%d %H:%M:%S"))

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

    try:
        smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        smtp.login(sender, password)
        smtp.send_message(message)
        smtp.quit()
    except Exception as e:
        st.error(f"メールエラー: {e}")

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
# 稼働制御
# =========================
manual = st.checkbox("🧪 手動ON（テスト）", value=False)

# 寄付き5分のみ稼働
time_run = (hour == 9 and minute <= 5)

run_bot = manual or time_run

st.write("BOT状態:", "🟢 ON" if run_bot else "🔴 OFF")

# 更新速度（寄付きは1分）
refresh_sec = 60 if run_bot else None

# =========================
# スキャン
# =========================
if run_bot:

    results = []
    progress = st.progress(0)

    for i, code in enumerate(codes):
        try:
            ticker = yf.Ticker(f"{code}.T")

            # 1分足
            df = ticker.history(period="5d", interval="1m")

            if df.empty or len(df) < 30:
                continue

            # 日足取得（前日終値）
            daily = ticker.history(period="3d")
            if len(daily) < 2:
                continue

            prev_close = daily["Close"].iloc[-2]

            latest = df.iloc[-1]

            # =========================
            # ギャップ
            # =========================
            gap = (latest["Open"] - prev_close) / prev_close

            if gap < 0.02 or gap > 0.06:
                continue

            # =========================
            # 出来高
            # =========================
            vol_ma = df["Volume"].rolling(20).mean().iloc[-1]

            if vol_ma == 0:
                continue

            vol_ratio = latest["Volume"] / vol_ma

            if vol_ratio < 2.0:
                continue

            # =========================
            # ブレイク
            # =========================
            high_5 = df["High"].rolling(5).max().iloc[-2]

            if latest["Close"] <= high_5:
                continue

            # =========================
            # エントリー
            # =========================
            entry = latest["Close"]
            stop = latest["Low"]

            risk = entry - stop

            if risk <= 0:
                continue

            # ボラ除外
            if (risk / entry) > 0.03:
                continue

            target = entry + risk * 2
            rr = (target - entry) / risk

            if rr < 2:
                continue

            # =========================
            # 通知（重複防止）
            # =========================
            key = code

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

            # =========================
            # 結果
            # =========================
            results.append({
                "コード": code,
                "銘柄名": name_dict.get(code, ""),
                "価格": round(entry,1),
                "ギャップ%": round(gap*100,1),
                "出来高倍率": round(vol_ratio,1),
                "RR": round(rr,2)
            })

        except Exception:
            continue

        progress.progress((i+1)/len(codes))

    # =========================
    # 表示
    # =========================
    if results:
        df_res = pd.DataFrame(results).sort_values("RR", ascending=False)

        st.subheader("🔥 寄付きチャンス銘柄")
        st.dataframe(df_res, width="stretch")

        st.subheader("📊 TradingView")
        for i, row in df_res.iterrows():
            st.link_button(
                f"{row['コード']} {row['銘柄名']}",
                f"https://jp.tradingview.com/symbols/TSE-{row['コード']}/"
            )
    else:
        st.warning("該当銘柄なし（条件が厳しめ）")

# =========================
# 自動更新
# =========================
if run_bot and refresh_sec:
    time.sleep(refresh_sec)
    st.rerun()
