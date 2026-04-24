import streamlit as st
import yfinance as yf
import pandas as pd
import time
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import pytz

# =========================
# 基本設定
# =========================
st.set_page_config(page_title="寄付きスキャナー（結果表示修正版）", layout="wide")
st.title("🔥 寄付き超精密スキャナー（結果表示・階層構造対策済）")

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

# 時間設定
JST = pytz.timezone("Asia/Tokyo")
now = datetime.now(JST)
st.write(f"現在時刻: {now.strftime('%H:%M:%S')} (JST)")

# 判定時間を9:30まで設定
is_open_time = (now.hour == 9 and now.minute <= 30)

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
        return pd.DataFrame([["8306", "三菱UFJ"], ["9984", "ソフトバンクG"], ["4568", "第一三共"]])

df_codes = load_codes()
codes = df_codes[0].astype(str).tolist()
name_dict = dict(zip(df_codes[0].astype(str), df_codes[1]))

run = st.checkbox("🚀 スキャン開始", value=True)

# =========================
# メインループ
# =========================
if run:
    if is_open_time:
        results = []
        alerts = []
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, code in enumerate(codes):
            try:
                # 【修正1】直近2日分を取得し、階層構造を強制解除
                df = yf.download(f"{code}.T", period="2d", interval="1m", progress=False)

                if df.empty:
                    continue

                # 【修正2】マルチインデックス対策：カラムをフラットにする
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                # 今日のデータのみ抽出
                today_str = now.strftime('%Y-%m-%d')
                df_today = df[df.index.strftime('%Y-%m-%d') == today_str].copy()

                if len(df_today) < 3:
                    continue

                # 各値の取得（型エラー防止のため .iloc[-1] を徹底）
                c_now = float(df_today["Close"].iloc[-1])
                o_start = float(df_today["Open"].iloc[0])
                h_max = float(df_today["High"].max())
                l_min = float(df_today["Low"].min())
                v_last = float(df_today["Volume"].iloc[-1])
                v_avg = float(df_today["Volume"].mean())

                # VWAP計算
                vwap = ((df_today["Close"] * df_today["Volume"]).cumsum() / df_today["Volume"].cumsum()).iloc[-1]

                # --- 判定ロジック ---
                cond_vwap = c_now > vwap
                cond_break = c_now >= (h_max * 0.995) # ほぼ高値圏
                cond_vol = (v_last > v_avg * 1.1)
                cond_plus = c_now > o_start

                if cond_vwap and cond_break and cond_vol and cond_plus:
                    results.append({
                        "コード": code,
                        "銘柄名": name_dict.get(code, ""),
                        "現在値": round(c_now, 1),
                        "出来高比": round(v_last / v_avg, 2)
                    })

                    if code not in st.session_state.sent_codes:
                        alerts.append(f"🔥 {code} {name_dict.get(code,'')} ({round(c_now,1)}円)")
                        st.session_state.sent_codes.add(code)

            except Exception as e:
                continue
            
            progress_bar.progress((i + 1) / len(codes))
            status_text.text(f"スキャン中: {code}")

        # --- 結果表示エリア ---
        if alerts:
            send_mail("\n".join(alerts))
            st.toast(f"📧 {len(alerts)}件のメールを送信しました")

        if results:
            st.subheader("✅ 条件合致銘柄")
            # テーブル形式でハッキリ表示
            st.table(pd.DataFrame(results))
            
            # 詳細リンク
            for res in results:
                st.link_button(f"📊 {res['コード']} {res['銘柄名']} を開く", f"https://jp.tradingview.com/symbols/TSE-{res['コード']}/")
        else:
            st.warning("⚠️ 現在、スキャン条件を満たす銘柄はありません。データが反映されるまでお待ちください。")

        time.sleep(60)
        st.rerun()
    else:
        st.info("⏰ 待機中：寄付き（9:00〜9:30）に自動でスキャンを開始します。")
else:
    st.warning("スキャナー停止中")
