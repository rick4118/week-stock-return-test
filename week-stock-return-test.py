import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# 設定網頁標題與排版
st.set_page_config(
    page_title="周K 自選股回測器 (受保護)",
    page_icon="📈",
    layout="wide"
)

# --- 密碼保護功能 ---
def check_password():
    """如果密碼正確則回傳 True，否則顯示輸入框並回傳 False"""
    def password_entered():
        if st.session_state["password"] == "592888":  # 👈 在這裡設定您的專屬密碼！
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔒 系統安全驗證")
        st.text_input(
            "請輸入密碼以存取周K 自選股回測器：",
            type="password",
            on_change=password_entered, 
            key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        st.title("🔒 系統安全驗證")
        st.text_input(
            "請輸入密碼以存取周K 自選股回測器：",
            type="password",
            on_change=password_entered, 
            key="password"
        )
        st.error("❌ 密碼錯誤，請重新輸入！")
        return False
    else:
        return True

if check_password():
    # --- 核心計算邏輯 ---
    def compute_macd(df, fast=12, slow=26, signal=9):
        df['EMA_fast'] = df['Close'].ewm(span=fast, adjust=False).mean()
        df['EMA_slow'] = df['Close'].ewm(span=slow, adjust=False).mean()
        df['DIF'] = df['EMA_fast'] - df['EMA_slow']
        df['MACD'] = df['DIF'].ewm(span=signal, adjust=False).mean()
        df['OSC'] = df['DIF'] - df['MACD']
        return df

    def backtest_single_stock(ticker, start_date, end_date, max_hold_weeks=12):
        try:
            df = yf.download(ticker, start=start_date, end=end_date, interval="1wk", auto_adjust=False, progress=False)
            if df.empty:
                return None, "無歷史資料"
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df.dropna(subset=["Close"])
            if len(df) < 35:
                return None, "資料筆數過少無法計算 MACD"
            
            df = compute_macd(df)
            
            trades = []
            in_position = False
            buy_price = 0
            buy_date = None
            weeks_held = 0
            
            for i in range(2, len(df)):
                current_date = df.index[i]
                current_close = float(df['Close'].iloc[i])
                
                osc_prev = float(df['OSC'].iloc[i-1])
                osc_curr = float(df['OSC'].iloc[i])
                
                # 買入訊號: OSC 連續兩周 > 0 且本周大於上周 (紅柱增長)
                buy_signal = (osc_prev > 0) and (osc_curr > 0) and (osc_curr > osc_prev)
                
                # 賣出訊號: OSC 變小(紅柱縮短或轉綠) 或是 超過最大持有週數
                sell_signal = (osc_curr < osc_prev) or (weeks_held >= max_hold_weeks)
                
                if not in_position:
                    if buy_signal:
                        in_position = True
                        buy_price = current_close
                        buy_date = current_date
                        weeks_held = 0
                else:
                    weeks_held += 1
                    if sell_signal:
                        profit_loss = (current_close - buy_price) / buy_price
                        trades.append({
                            "買入日期": buy_date.strftime('%Y-%m-%d'),
                            "買入價格": round(buy_price, 2),
                            "賣出日期": current_date.strftime('%Y-%m-%d'),
                            "賣出價格": round(current_close, 2),
                            "持有週數": weeks_held,
                            "報酬率%": round(profit_loss * 100, 2)
                        })
                        in_position = False
                        weeks_held = 0
                        
            # 若最後一筆交易尚未出場，以最後收盤價強行出場估算
            if in_position:
                last_close = float(df['Close'].iloc[-1])
                profit_loss = (last_close - buy_price) / buy_price
                trades.append({
                    "買入日期": buy_date.strftime('%Y-%m-%d'),
                    "買入價格": round(buy_price, 2),
                    "賣出日期": df.index[-1].strftime('%Y-%m-%d') + " (未平倉)",
                    "賣出價格": round(last_close, 2),
                    "持有週數": weeks_held,
                    "報酬率%": round(profit_loss * 100, 2)
                })
                
            return trades, None
        except Exception as e:
            return None, str(e)

    # --- App 主介面 ---
    st.title("📈 周K 自選股回測器")
    st.write("設定您的自選股名單與回測區間，檢驗策略績效！")

    # 側邊欄設定
    st.sidebar.header("⚙️ 回測參數設定")
    start_date_val = st.sidebar.date_input("開始日期:", datetime.now() - pd.Timedelta(days=365*3))
    end_date_val = st.sidebar.date_input("結束日期:", datetime.now())
    max_hold_weeks = st.sidebar.slider("最大持有週數 (強制出場):", 2, 24, 12)

    default_tickers = "2330, 1519, 2603, 2605, 3491, 8086"
    tickers_input = st.text_area(
        "輸入自選股代號 (支援空格、逗號、換行分隔):",
        value=default_tickers,
        height=100
    )

    run_button = st.button("🚀 開始歷史回測", use_container_width=True)

    if run_button:
        raw_input = tickers_input
        for char in [',', ';', '\n', '\t', '，', '；']:
            raw_input = raw_input.replace(char, ' ')
        cleaned_tickers = [t.strip() for t in raw_input.split(' ') if t.strip()]

        if not cleaned_tickers:
            st.warning("⚠️ 請輸入至少一個股票代號！")
        else:
            formatted_tickers = [f"{t}.TW" if "." not in t else t for t in cleaned_tickers]
            
            summary_results = []
            all_trades_details = {}
            
            with st.spinner("⏳ 回測運算中..."):
                for ticker in formatted_tickers:
                    trades, err = backtest_single_stock(
                        ticker, 
                        start_date_val.strftime('%Y-%m-%d'), 
                        end_date_val.strftime('%Y-%m-%d'),
                        max_hold_weeks
                    )
                    if err:
                        summary_results.append({
                            "股票代碼": ticker,
                            "交易次數": 0,
                            "勝率%": "N/A",
                            "累積報酬率%": "N/A",
                            "狀態": f"錯誤: {err}"
                        })
                    elif not trades:
                        summary_results.append({
                            "股票代碼": ticker,
                            "交易次數": 0,
                            "勝率%": 0.0,
                            "累積報酬率%": 0.0,
                            "狀態": "無觸發交易"
                        })
                    else:
                        # 計算個股回測指標
                        total_trades = len(trades)
                        win_trades = sum(1 for t in trades if t["報酬率%"] > 0)
                        win_rate = round((win_trades / total_trades) * 100, 2)
                        
                        # 簡單加總報酬率 (複利亦可用乘積，此處採簡單加總)
                        total_return = round(sum(t["報酬率%"] for t in trades), 2)
                        
                        summary_results.append({
                            "股票代碼": ticker,
                            "交易次數": total_trades,
                            "勝率%": win_rate,
                            "累積報酬率%": total_return,
                            "狀態": "成功"
                        })
                        all_trades_details[ticker] = pd.DataFrame(trades)
            
            # --- 顯示總覽結果 ---
            st.subheader("📊 自選股回測總覽績效")
            summary_df = pd.DataFrame(summary_results)
            st.dataframe(summary_df, use_container_width=True)
            
            # --- 顯示個別交易明細 ---
            if all_trades_details:
                st.subheader("📋 個股詳細交易明細")
                selected_ticker = st.selectbox("選擇欲檢視明細之個股:", list(all_trades_details.keys()))
                if selected_ticker:
                    st.write(f
