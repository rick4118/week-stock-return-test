import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

# 設定網頁標題與排版
st.set_page_config(
    page_title="自選股區間持有報酬率計算器 (受保護)",
    page_icon="📈",
    layout="wide"
)

# --- 密碼保護功能 ---
def check_password():
    """如果密碼正確則回傳 True，否則顯示輸入框並回傳 False"""
    def password_entered():
        if st.session_state["password"] == "592888":  # 👈 密碼設定
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔒 系統安全驗證")
        st.text_input(
            "請輸入密碼以存取自選股區間持有計算器：",
            type="password",
            on_change=password_entered,
            key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        st.title("🔒 系統安全驗證")
        st.text_input(
            "請輸入密碼以存取自選股區間持有計算器：",
            type="password",
            on_change=password_entered,
            key="password"
        )
        st.error("❌ 密碼錯誤，請重新輸入！")
        return False
    else:
        return True

if check_password():
    st.title("📈 自選股區間持有報酬率計算器")
    st.write("輸入您選定股票的**買入日期**與**賣出日期**，系統將自動下載股價並計算出該段期間的持有報酬率（不涉及任何技術指標策略）。")

    # 側邊欄設定
    st.sidebar.header("📅 回測區間設定")
    buy_date_val = st.sidebar.date_input("1. 篩選/買入日期 (Buy Date):", datetime.now() - pd.Timedelta(days=365))
    sell_date_val = st.sidebar.date_input("2. 結束/賣出日期 (Sell Date):", datetime.now())
    
    price_type = st.sidebar.selectbox("3. 計算基準價格:", ["收盤價 (Close)", "開盤價 (Open)"])
    col_name = "Close" if "收盤價" in price_type else "Open"

    # 自選股輸入
    default_tickers = "2330, 1519, 2603, 2605, 3491, 8086"
    tickers_input = st.text_area(
        "輸入自選股代號 (支援空格、逗號、換行分隔):",
        value=default_tickers,
        height=100
    )

    run_button = st.button("🚀 開始計算報酬率", use_container_width=True)

    if run_button:
        raw_input = tickers_input
        for char in [',', ';', '\n', '\t', '，', '；']:
            raw_input = raw_input.replace(char, ' ')
        cleaned_tickers = [t.strip() for t in raw_input.split(' ') if t.strip()]

        if not cleaned_tickers:
            st.warning("⚠️ 請輸入至少一個股票代號！")
        elif buy_date_val >= sell_date_val:
            st.error("❌ 買入日期必須早於賣出日期！")
        else:
            # 自動補上台股尾綴
            formatted_tickers = [f"{t}.TW" if "." not in t else t for t in cleaned_tickers]
            
            results = []
            
            # 為確保能抓到精準的開盤/收盤價（避開假日無開盤），抓取前後多幾天的數據
            download_start = (buy_date_val - pd.Timedelta(days=10)).strftime('%Y-%m-%d')
            download_end = (sell_date_val + pd.Timedelta(days=10)).strftime('%Y-%m-%d')

            with st.spinner("⏳ 正在下載股價並計算中..."):
                for ticker in formatted_tickers:
                    try:
                        # 下載日 K 資料
                        df = yf.download(ticker, start=download_start, end=download_end, auto_adjust=False, progress=False)
                        if df.empty:
                            results.append({"股票代碼": ticker, "買入日期": "-", "買入價格": "-", "賣出日期": "-", "賣出價格": "-", "報酬率%": "-", "備註": "查無此股票或歷史資料"})
                            continue
                        
                        if isinstance(df.columns, pd.MultiIndex):
                            df.columns = df.columns.get_level_values(0)
                        
                        df = df.dropna(subset=[col_name])
                        
                        # 尋找與設定日期最接近的交易日 ( >= 買入日)
                        buy_df = df[df.index >= pd.to_datetime(buy_date_val)]
                        # 尋找與設定日期最接近的交易日 ( <= 賣出日)
                        sell_df = df[df.index <= pd.to_datetime(sell_date_val)]
                        
                        if buy_df.empty or sell_df.empty:
                            results.append({"股票代碼": ticker, "買入日期": "-", "買入價格": "-", "賣出日期": "-", "賣出價格": "-", "報酬率%": "-", "備註": "此區間內無交易數據"})
                            continue
                            
                        actual_buy_row = buy_df.iloc[0]
                        actual_sell_row = sell_df.iloc[-1]
                        
                        actual_buy_date = buy_df.index[0].strftime('%Y-%m-%d')
                        actual_sell_date = sell_df.index[-1].strftime('%Y-%m-%d')
                        
                        if pd.to_datetime(actual_buy_date) > pd.to_datetime(actual_sell_date):
                            results.append({"股票代碼": ticker, "買入日期": "-", "買入價格": "-", "賣出日期": "-", "賣出價格": "-", "報酬率%": "-", "備註": "有效買入日晚於賣出日"})
                            continue
                        
                        buy_price = float(actual_buy_row[col_name])
                        sell_price = float(actual_sell_row[col_name])
                        
                        # 計算報酬率
                        profit_loss = (sell_price - buy_price) / buy_price
                        
                        results.append({
                            "股票代碼": ticker,
                            "實際買入日期": actual_buy_date,
                            f"買入{price_type[:3]}": round(buy_price, 2),
                            "實際賣出日期": actual_sell_date,
                            f"賣出{price_type[:3]}": round(sell_price, 2),
                            "報酬率%": round(profit_loss * 100, 2),
                            "備註": "成功"
                        })
                    except Exception as e:
                        results.append({"股票代碼": ticker, "買入日期": "-", "買入價格": "-", "賣出日期": "-", "賣出價格": "-", "報酬率%": "-", "備註": f"錯誤: {str(e)}"})
            
            # --- 顯示結果表格 ---
            st.subheader(f"📊 自選股區間持有報酬率 ({buy_date_val} 至 {sell_date_val})")
            res_df = pd.DataFrame(results)
            st.dataframe(res_df, use_container_width=True)
            
            # 統計平均表現
            valid_returns = res_df[res_df["報酬率%"] != "-"]["報酬率%"].astype(float)
            if not valid_returns.empty:
                avg_return = round(valid_returns.mean(), 2)
                win_rate = round((sum(1 for r in valid_returns if r > 0) / len(valid_returns)) * 100, 2)
                
                col1, col2, col3 = st.columns(3)
                col1.metric("📈 平均報酬率", f"{avg_return} %")
                col2.metric("🎯 勝率 (正報酬比例)", f"{win_rate} %")
                col3.metric("📋 有效計算檔數", f"{len(valid_returns)} / {len(formatted_tickers)} 檔")
