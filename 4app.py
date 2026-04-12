import streamlit as st
import yfinance as yf
import pandas as pd
import time
import smtplib
from email.mime.text import MIMEText
import os

st.set_page_config(page_title="最強スキャナー GOD", layout="wide")

st.title("👑 最強スキャナー GOD（勝率 × RR）")

# =========================
# メール通知関数
# =========================
def send_mail(msg):
    sender = "ediix.164@gmail.com"
    password = "srhg uzgk lccr yssk"
    receiver = "ediix.164@gmail.com"

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

if "selected_code" not in st.session_state:
    st.session_state.selected_code = None

if "trade_log" not in st.session_state:
    st.session_state.trade_log = []

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

auto_refresh = st.checkbox("🔄 自動更新", value=False)

# =========================
# 勝率辞書
# =========================
win_rate_dict = {}

if st.session_state.trade_log:
    df_log = pd.DataFrame(st.session_state.trade_log)
    summary = df_log.groupby("サイン")["結果"].apply(
        lambda x: (x == "勝ち").mean()
    )
    win_rate_dict = summary.to_dict()

# =========================
# スキャン
# =========================
if True:

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

            # ===== メール通知（ここ重要）=====
            if rr >= 2:
                msg = f"""
🔥 {code} {name_dict.get(code, "")}
{signal}
IN:{round(entry,1)}
RR:{round(rr,2)}
"""
                send_mail(msg)

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

    df1 = st.session_state.scan_results

    st.subheader("🔥 勝てる銘柄だけ")

    st.dataframe(df1, use_container_width=True)

    for i, row in df1.iterrows():
        if st.button(f"{row['コード']} {row['銘柄名']}", key=f"btn_{i}"):
            st.session_state.selected_code = row["コード"]

# =========================
# チャート
# =========================
if st.session_state.selected_code:
    code = st.session_state.selected_code
    st.link_button("📊 チャート", f"https://jp.tradingview.com/symbols/TSE-{code}/")

# =========================
# CSV保存
# =========================
LOG_FILE = "trade_history.csv"

if "trade_log_loaded" not in st.session_state:
    if os.path.exists(LOG_FILE):
        try:
            st.session_state.trade_log = pd.read_csv(LOG_FILE).to_dict('records')
        except:
            st.session_state.trade_log = []
    st.session_state.trade_log_loaded = True

# =========================
# トレード記録
# =========================
st.subheader("📊 トレード記録")

with st.form(key="trade_record_form"):
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        t_code = st.text_input("コード", value=st.session_state.selected_code if st.session_state.selected_code else "")

    with col2:
        t_entry = st.number_input("IN", min_value=0.0, step=1.0)

    with col3:
        t_exit = st.number_input("OUT", min_value=0.0, step=1.0)

    with col4:
        t_signal = st.selectbox("サイン", ["🟢 押し目反転", "🔥 ブレイク", "⚡ 初動"])

    submit_button = st.form_submit_button(label="保存")

    if submit_button:
        if t_entry > 0 and t_exit > 0:
            result = "勝ち" if t_exit > t_entry else "負け"

            new_data = {
                "コード": t_code,
                "サイン": t_signal,
                "エントリー": t_entry,
                "決済": t_exit,
                "結果": result
            }

            st.session_state.trade_log.append(new_data)
            pd.DataFrame(st.session_state.trade_log).to_csv(LOG_FILE, index=False)

            st.success("保存完了")

# =========================
# 自動更新
# =========================
if auto_refresh:
    time.sleep(300)
    st.rerun()
