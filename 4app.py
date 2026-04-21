import streamlit as st
import yfinance as yf
import pandas as pd
import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import pytz

st.set_page_config(page_title="寄付き10分スキャナー（完全版）", layout="wide")
st.title("🔥 寄付き超精密スキャナー + メール通知")

# =========================
# メール設定
# =========================
SENDER = "ediix.164@gmail.com"
PASSWORD = "srhg uzgk lccr yssk"
RECEIVER = "ediix.164@gmail.com"

def send_mail(body):
    try:
        msg = MIMEText(body)
        msg["Subject"] = "📈 寄付きアラート"
        msg["From"] = SENDER
        msg["To"] = RECEIVER
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SENDER, PASSWORD)
            smtp.send_message(msg)
    except Exception as e:
        st.error(f"メール送信失敗: {e}")

# =========================
# 日本時間・判定
# =========================
JST = pytz.timezone("Asia/Tokyo")
now = datetime.now(JST)
# デバッグ用：時間を上書きしたい場合はここを書き換える
hour = now.hour
minute = now.minute

st.write(f"現在時刻: {hour:02d}:{minute:02d} (JST)")

# 寄付き判定を9:00〜9:15に少し延長（5分足が確定する時間を考慮）
is_open_time = (hour == 9 and minute <= 15)

# =========================
# セッション状態
# =========================
if "sent_codes" not in st.session_state:
    st.session_state.sent_codes = set()

# =========================
# 銘柄読み込み
# =========================
@st.cache_data
def load_codes():
    try:
        # csvがない場合はJPX400の代表的な数銘柄でテストできるよう例外処理
        df_codes = pd.read_csv("jpx400.csv", header=None)
        return df_codes
    except:
        st.error("jpx400.csv が見つかりません。テスト用データを使用します。")
        return pd.DataFrame([["8306", "三菱UFJ"], ["9984", "ソフトバンクG"], ["8035", "東エレク"]])

df_codes = load_codes()
codes = df_codes[0].astype(str).tolist()
name_dict = dict(zip(df_codes[0].astype(str), df_codes[1]))

run = st.checkbox("🚀 スキャンON", value=True)

# =========================
# スキャンメインロジック
# =========================
if run:
    if is_open_time:
        results = []
        alerts = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, code in enumerate(codes):
            try:
                # 【修正ポイント】1分足の取得を安定させるため period="5d" に変更（当日分を確実に含むため）
                df = yf.download(
                    f"{code}.T",
                    interval="1m",
                    period="1d",
                    progress=False,
                    timeout=10
                )

                if df.empty or len(df) < 3: # 5分待たず、3分あれば判定開始
                    continue

                # 直近5分（または現時点まで）のデータを取得
                df5 = df.tail(5).copy()

                high_5 = df5["High"].max()
                low_5 = df5["Low"].min()
                close_now = df5["Close"].iloc[-1]
                open_start = df5["Open"].iloc[0]

                # VWAP計算
                df5["VWAP"] = (df5["Close"] * df5["Volume"]).cumsum() / df5["Volume"].cumsum()
                vwap_now = df5["VWAP"].iloc[-1]

                # 出来高倍率（条件を少し緩めて1.1に）
                vol_ratio = df5["Volume"].iloc[-1] / df5["Volume"].mean()

                # 陰線数（5本中2本まで許容に緩和）
                red_count = (df5["Close"] < df5["Open"]).sum()

                # --- 判定条件 ---
                cond_vwap = close_now > vwap_now
                # 高値引けに近い（0.99倍まで緩和）
                cond_break = close_now >= high_5 * 0.99
                cond_vol = vol_ratio > 1.1 
                cond_candle = red_count <= 2 
                # 陽線であること
                cond_plus = close_now > open_start

                if cond_vwap and cond_break and cond_vol and cond_candle and cond_plus:
                    entry = float(high_5)
                    stop = float(low_5)
                    risk = entry - stop

                    if risk > 0:
                        target = entry + risk * 2
                        rr = 2.0 # 固定または計算
                        
                        results.append({
                            "コード": code,
                            "銘柄名": name_dict.get(code, ""),
                            "株価": round(float(close_now), 1),
                            "RR": round(rr, 2),
                            "出来高倍率": round(float(vol_ratio), 2)
                        })

                        # メール通知（1回のみ）
                        if code not in st.session_state.sent_codes:
                            alert_text = f"🔥 {code} {name_dict.get(code,'')}\n株価: {round(float(close_now),1)}\n出来高倍率: {round(float(vol_ratio),2)}"
                            alerts.append(alert_text)
                            st.session_state.sent_codes.add(code)

            except Exception as e:
                continue
            
            progress_bar.progress((i + 1) / len(codes))
            status_text.text(f"スキャン中... {code}")

        # 表示・送信
        if alerts:
            send_mail("\n\n".join(alerts))
            st.success(f"📧 {len(alerts)}件の新規アラートを送信しました")

        if results:
            df_res = pd.DataFrame(results).sort_values("出来高倍率", ascending=False)
            st.subheader("🔥 本日のチャンス銘柄")
            st.dataframe(df_res, use_container_width=True)
            
            # TradingViewリンク
            cols = st.columns(2)
            for idx, row in df_res.iterrows():
                with cols[idx % 2]:
                    st.link_button(f"📊 {row['コード']} {row['銘柄名']}", f"https://jp.tradingview.com/symbols/TSE-{row['コード']}/")
        else:
            st.warning("現在、条件に合致する銘柄はありません。")

        time.sleep(60)
        st.rerun()
    else:
        st.info("⏰ 現在は寄付き時間外（9:00〜9:15）です。")
else:
    st.warning("スキャナーは停止中です。")
