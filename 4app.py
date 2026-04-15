import streamlit as st
import yfinance as yf
import pandas as pd
import time
from datetime import datetime
import pytz

st.set_page_config(page_title="寄付き5分スキャナー", layout="wide")
st.title("🔥 寄付き5分 超精密スキャナー")

# =========================
# 日本時間
# =========================
JST = pytz.timezone("Asia/Tokyo")
now = datetime.now(JST)
hour = now.hour
minute = now.minute

# =========================
# 寄付き5分判定
# =========================
is_open_time = (hour == 9 and minute <= 5)

# =========================
# 銘柄読み込み
# =========================
df_codes = pd.read_csv("jpx400.csv", header=None)
codes = df_codes[0].astype(str).tolist()
name_dict = dict(zip(df_codes[0].astype(str), df_codes[1]))

# =========================
# UI
# =========================
run = st.checkbox("🚀 スキャンON", value=True)

# =========================
# スキャン
# =========================
if run and is_open_time:

    results = []
    progress = st.progress(0)

    for i, code in enumerate(codes):
        try:
            # 1分足（当日）
            df = yf.download(
                f"{code}.T",
                interval="1m",
                period="1d",
                progress=False
            )

            if len(df) < 5:
                continue

            # 最初の5本だけ使う
            df5 = df.iloc[:5]

            # =========================
            # 指標
            # =========================
            open_price = df5["Open"].iloc[0]
            high_5 = df5["High"].max()
            low_5 = df5["Low"].min()
            close_now = df5["Close"].iloc[-1]

            # VWAP
            df5["VWAP"] = (df5["Close"] * df5["Volume"]).cumsum() / df5["Volume"].cumsum()
            vwap_now = df5["VWAP"].iloc[-1]

            # 出来高倍率（1分平均）
            vol_ratio = df5["Volume"].iloc[-1] / df5["Volume"].mean()

            # 陰線チェック
            red_candle = any(df5["Close"] < df5["Open"])

            # =========================
            # 条件
            # =========================
            cond_vwap = close_now > vwap_now
            cond_break = close_now >= high_5 * 0.999
            cond_vol = vol_ratio > 1.5
            cond_no_red = not red_candle

            if cond_vwap and cond_break and cond_vol and cond_no_red:

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
                    "エントリー": round(entry,1),
                    "損切り": round(stop,1),
                    "利確": round(target,1),
                    "RR": round(rr,2),
                    "出来高倍率": round(vol_ratio,2)
                })

        except:
            continue

        progress.progress((i+1)/len(codes))

    # =========================
    # 表示
    # =========================
    if results:
        df_result = pd.DataFrame(results)\
            .sort_values("出来高倍率", ascending=False)\
            .head(10)

        st.subheader("🔥 寄付き最強候補")
        st.dataframe(df_result, width='stretch')

        st.subheader("📊 即トレード用リンク")
        for i, row in df_result.iterrows():
            st.link_button(
                f"{row['コード']} {row['銘柄名']}",
                f"https://jp.tradingview.com/symbols/TSE-{row['コード']}/"
            )
    else:
        st.warning("該当なし（＝無理に入るな）")

# =========================
# 自動更新（1分）
# =========================
if run and is_open_time:
    time.sleep(60)
    st.rerun()
