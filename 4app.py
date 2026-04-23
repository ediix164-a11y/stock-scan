import streamlit as st
import yfinance as yf
import pandas as pd
import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import pytz

st.set_page_config(page_title="寄付き10分スキャナー（安定版）", layout="wide")
st.title("🔥 寄付き超精密スキャナー（データ取得強化版）")

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
hour = now.hour
minute = now.minute

st.write(f"現在時刻: {hour:02d}:{minute:02d} (JST)")

# 判定時間を9:30まで広げ、データの反映待ちに対応
is_open_time = (hour == 9 and minute <= 30)

if "sent_codes" not in st.session_state:
    st.session_state.sent_codes = set()

# =========================
# 銘柄読み込み
# =========================
@st.cache_data
def load_codes():
    try:
        df_codes = pd.read_csv("jpx400.csv", header=None)
        return df_codes
    except:
        return pd.DataFrame([["8306", "三菱UFJ"], ["9984", "SBG"], ["4568", "第一三共"]])

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
                # 【最重要修正】period="1d"だと朝イチは空になることが多いため、"2d"で取得して今日分を抽出
                df = yf.download(
                    f"{code}.T",
                    interval="1m",
                    period="2d",
                    progress=False,
                    timeout=10
                )

                if df.empty:
                    continue

                # 日本時間の今日の日付のデータのみに絞り込み
                today_str = now.strftime('%Y-%m-%d')
                df_today = df.loc[df.index.strftime('%Y-%m-%d') == today_str].copy()

                if len(df_today) < 2: # 最低2分あれば動かす
                    continue

                # Seriesからスカラ値へ確実に変換 (.item() を使用)
                high_5 = df_today["High"].max().item()
                low_5 = df_today["Low"].min().item()
                close_now = df_today["Close"].iloc[-1].item()
                open_start = df_today["Open"].iloc[0].item()
                volume_last = df_today["Volume"].iloc[-1].item()
                volume_avg = df_today["Volume"].mean().item()

                # VWAP計算
                vwap_now = ((df_today["Close"] * df_today["Volume"]).cumsum() / df_today["Volume"].cumsum()).iloc[-1].item()

                # 出来高倍率
                vol_ratio = volume_last / volume_avg if volume_avg > 0 else 0

                # 判定条件（さらに実戦的に調整）
                cond_vwap = close_now > vwap_now
                cond_break = close_now >= (high_5 * 0.99) # ほぼ高値圏
                cond_vol = vol_ratio > 1.0 # 寄付きは出来高が不安定なので1.0以上に緩和
                cond_plus = close_now > open_start # 始値より上で推移

                if cond_vwap and cond_break and cond_vol and cond_plus:
                    results.append({
                        "コード": code,
                        "銘柄名": name_dict.get(code, ""),
                        "株価": round(close_now, 1),
                        "出来高倍率": round(vol_ratio, 2)
                    })

                    if code not in st.session_state.sent_codes:
                        alert_text = f"🔥 {code} {name_dict.get(code,'')}\n株価: {round(close_now,1)}\n出来高倍率: {round(vol_ratio,2)}"
                        alerts.append(alert_text)
                        st.session_state.sent_codes.add(code)

            except Exception as e:
                # エラー内容を確認したい場合は st.write(e)
                continue
            
            progress_bar.progress((i + 1) / len(codes))
            status_text.text(f"スキャン中... {code}")

        if alerts:
            send_mail("\n\n".join(alerts))
            st.success(f"📧 {len(alerts)}件のアラート送信")

        if results:
            df_res = pd.DataFrame(results).sort_values("出来高倍率", ascending=False)
            st.subheader("🔥 寄付き初動候補")
            st.dataframe(df_res, use_container_width=True)
            
            for idx, row in df_res.head(5).iterrows():
                st.link_button(f"📊 {row['コード']} {row['銘柄名']}", f"https://jp.tradingview.com/symbols/TSE-{row['コード']}/")
        else:
            st.warning("条件に合う銘柄が見つかりませんでした。データ反映待ちの可能性があります。")

        time.sleep(60)
        st.rerun()
    else:
        st.info("⏰ 寄付き時間外（9:00〜9:30）です。")
else:
    st.warning("停止中")
