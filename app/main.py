import sys
import os

# ضبط مسار المشروع لتفادي أخطاء الاستيراد
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

# إعدادات الصفحة
st.set_page_config(
    page_title="محلل الأسهم المصرية - المطور",
    page_icon="📈",
    layout="wide"
)

# ===== Caching لتقليل الضغط على yfinance وزيادة السرعة =====
@st.cache_data(ttl=300)
def get_stock_data(symbol, period):
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period)
    return df

@st.cache_data(ttl=3600)
def get_ath(symbol):
    ticker = yf.Ticker(symbol)
    full_df = ticker.history(period="max")
    return full_df['High'].max() if not full_df.empty else None

# عنوان لوحة التحكم
st.title("📈 لوحة المتابعة وإدارة مخاطر القمم (EGX)")
st.caption("كشف القمم التاريخية، اتخاذ القرار، ونقاط الأمان")

# شريط جانبي لإدخال البيانات
st.sidebar.header("⚙️ إعدادات البحث")
stock_symbol = st.sidebar.text_input("رمز السهم:", value="ABUK").upper().strip()
period = st.sidebar.selectbox("الفترة الزمنية:", ["6mo", "1y", "2y", "5y", "max"], index=1)

if stock_symbol:
    full_symbol = f"{stock_symbol}.CA" if not stock_symbol.endswith(".CA") else stock_symbol

    try:
        with st.spinner("جاري تحميل البيانات..."):
            df = get_stock_data(full_symbol, period)
            ath_price = get_ath(full_symbol)

        if df.empty or len(df) < 20:
            st.warning("⚠️ البيانات غير كافية أو الرمز غير صحيح. تأكد من رمز السهم.")
            st.stop()

        # ===== حساب المؤشرات الفنية =====
        df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean() if len(df) >= 50 else df['EMA20']
        df['Vol_Avg20'] = df['Volume'].rolling(window=20).mean()

        last_close = df['Close'].iloc[-1]
        last_high = df['High'].iloc[-1]
        last_low = df['Low'].iloc[-1]
        last_vol = df['Volume'].iloc[-1]
        prev_close = df['Close'].iloc[-2]

        change = last_close - prev_close
        pct_change = (change / prev_close) * 100

        # ===== ملخص الجلسة =====
        st.subheader(f"📊 ملخص: {stock_symbol}")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("آخر إغلاق", f"{last_close:.2f} EGP", f"{change:+.2f} ({pct_change:+.2f}%)")
        col2.metric("أعلى الجلسة", f"{last_high:.2f} EGP")
        col3.metric("🏆 القمة التاريخية", f"{ath_price:.2f} EGP" if ath_price else "N/A")
        col4.metric("حجم التداول", f"{last_vol:,.0f}")

        # ===== حساب النقاط المحورية (Pivot Points) =====
        pivot = (last_high + last_low + last_close) / 3
        r1 = (2 * pivot) - last_low
        s1 = (2 * pivot) - last_high
        s2 = pivot - (last_high - last_low)
        stop_loss = s2 * 0.985

        st.markdown("---")
        st.subheader("🛡️ تقييم أمان القمم والقرار")

        is_near_ath = ath_price and (last_close >= ath_price * 0.97)

        if is_near_ath:
            st.error(f"⚠️ **تحذير: السهم قريب من القمة التاريخية ({ath_price:.2f} EGP)!**")
            st.write("🛑 **ممنوع الشراء بأسعار السوق الآن.** انتظر التصحيح أو إغلاق مؤكد فوق القمة.")
        elif last_close < s1:
            st.success("🟢 **السهم في منطقة دعم ممتازة للشراء.**")
        else:
            st.info("🔵 **السهم في منطقة حركة متوازنة.**")

        # ===== خطة التنفيذ =====
        st.markdown("### 📋 مناطق التنفيذ:")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**📉 شراء آمن (بعد التصحيح):**\n`{s2:.2f}` ← `{s1:.2f}` جنيه")
        with c2:
            st.markdown(f"**🚀 شراء اختراق:**\nفوق `{ath_price:.2f}` جنيه" if ath_price else "N/A")
        with c3:
            st.markdown(f"**🛑 حد وقف الخسارة:**\n`{stop_loss:.2f}` جنيه")

        # ===== رسم Candlestick تفاعلي واحترافي =====
        st.markdown("---")
        st.write("### 📉 الشارت التفاعلي (شموع يابانية + المتوسطات)")

        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'],
            low=df['Low'], close=df['Close'], name="السعر"
        ))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA20'], 
                                 line=dict(color='orange', width=1.5), name="EMA 20"))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA50'], 
                                 line=dict(color='deepskyblue', width=1.5), name="EMA 50"))
        
        # إضافة خط القمة التاريخية على الشارت
        if ath_price:
            fig.add_hline(y=ath_price, line_dash="dash", line_color="red",
                          annotation_text=f"ATH: {ath_price:.2f}", annotation_position="top left")

        fig.update_layout(
            xaxis_rangeslider_visible=False,
            height=500,
            margin=dict(l=10, r=10, t=30, b=10),
            template="plotly_dark"
        )
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("📋 عرض جدول البيانات التاريخية"):
            st.dataframe(df.sort_index(ascending=False), use_container_width=True)

    except Exception as e:
        st.error(f"❌ حدث خطأ أثناء جلب البيانات: {e}")
        st.info("تأكد من رمز السهم أو حاول مرة أخرى.")
