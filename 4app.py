import streamlit as st
import yfinance as yf
import pandas as pd
import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import pytz

st.set_page_config(page_title="寄付き5分スキャナー（通知付き）", layout="wide")
st.title("🔥 寄付き5分 超精密スキャナー + メール通知")

# =========================
# メール設定（ここ書き換え）
# =========================
SENDER = "ediix.164@gmail.com"
PASSWORD = "srhg uzgk lccr yssk"
RECEIVER = "ediix.164@gmail.com"

def send_mail(body):
    msg = MIMEText(body)
    msg["Subject"] = "📈 寄付きアラート"
    msg["From"] = SENDER
    msg["To"] = RECEIVER

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(SENDER, PASSWORD)
        smtp.send_message(msg)

# =========================
# 日本時間
# =========================
JST = pytz.timezone("Asia/Tokyo")
now = datetime.now(JST)
hour = now.hour
minute = now.minute

st.write(f"現在時刻: {hour}:{minute}")

# =========================
# 寄付き判定
# =========================
is_open_time = (hour == 9 and minute <= 10)

# =========================
# セッション
# =========================
if "sent_codes" not in st.session_state:
    st.session_state.sent_codes = set()

# =========================
# 銘柄
# =========================
df_codes = pd.read_csv("jpx400.csv", header=None)
codes = df_codes[0].astype(str).tolist()
name_dict = dict(zip(df_codes[0].astype(str), df_codes[1]))

# =========================
# ON/OFF
# =========================
run = st.checkbox("🚀 スキャンON", value=True)

# =========================
# スキャン
# =========================
if run and is_open_time:

    results = []
    alerts = []
    progress = st.progress(0)

    for i, code in enumerate(codes):
        try:
            df = yf.download(
                f"{code}.T",
                interval="1m",
                period="1d",
                progress=False
            )

            if df is None or len(df) < 5:
                continue

            df5 = df.iloc[:5].copy()

            high_5 = df5["High"].max()
            low_5 = df5["Low"].min()
            close_now = df5["Close"].iloc[-1]

            # VWAP
            df5["VWAP"] = (df5["Close"] * df5["Volume"]).cumsum() / df5["Volume"].cumsum()
            vwap_now = df5["VWAP"].iloc[-1]

            # 出来高倍率
            vol_ratio = df5["Volume"].iloc[-1] / df5["Volume"].mean()

            # 陰線許容
            red_count = (df5["Close"] < df5["Open"]).sum()

            # 条件（実戦版）
            cond_vwap = close_now > vwap_now
            cond_break = close_now >= high_5 * 0.995
            cond_vol = vol_ratio > 1.2
            cond_candle = red_count <= 1

            if cond_vwap and cond_break and cond_vol and cond_candle:

                entry = high_5
                stop = low_5
                risk = entry - stop

                if risk <= 0:
                    continue

                target = entry + risk * 2
                rr = (target - entry) / risk

                results.append({
                    "コード": code,
                    "銘柄名": name_dict.get(code, ""),
                    "株価": round(close_now,1),
                    "RR": round(rr,2),
                    "出来高倍率": round(vol_ratio,2)
                })

                # =========================
                # メール通知（RR高いものだけ）
                # =========================
                if rr >= 2:
                    key = f"{code}"

                    if key not in st.session_state.sent_codes:
                        alert_text = f"""
🔥 {code} {name_dict.get(code,"")}
株価: {round(close_now,1)}
RR: {round(rr,2)}
"""
                        alerts.append(alert_text)
                        st.session_state.sent_codes.add(key)

        except:
            continue

        progress.progress((i+1)/len(codes))

    # =========================
    # メール送信（まとめて）
    # =========================
    if alerts:
        send_mail("\n\n".join(alerts))
        st.success(f"📧 {len(alerts)}件メール送信")

    # =========================
    # 表示
    # =========================
    if results:
        df_result = pd.DataFrame(results)\
            .sort_values("出来高倍率", ascending=False)\
            .head(10)

        st.subheader("🔥 チャンス銘柄")
        st.dataframe(df_result, width="stretch")

        for i, row in df_result.iterrows():
            st.link_button(
                f"{row['コード']} {row['銘柄名']}",
                f"https://jp.tradingview.com/symbols/TSE-{row['コード']}/"
            )
    else:
        st.warning("該当なし（ノートレ日）")

else:
    st.info("⏰ 寄付き時間外 or OFF")

# =========================
# 1分更新
# =========================
if run and is_open_time:
    time.sleep(60)
    st.rerun()
