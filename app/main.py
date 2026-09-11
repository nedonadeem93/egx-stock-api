import sys
import os

# ضبط مسار المشروع لتفادي أخطاء الاستيراد (ImportError)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import streamlit as st
import pandas as pd
import yfinance as yf
# إعدادات الصفحة
st.set_page_config(
    page_title="محلل الأسهم المصرية | EGX Tracker",
    page_icon="📈",
    layout="wide"

# عنوان لوحة التحكم
st.title("📈 لوحة متابعة الأسهم المصرية (EGX)")
st.caption("نظام متابعة وتحليل خاص بك فقط")

# شريط جانبي لإدخال البيانات
st.sidebar.header("إعدادات البحث")
stock_symbol = st.sidebar.text_input("رمز السهم (مثال: COMI, TMGH, FWRY):", value="COMI").upper()
period = st.sidebar.selectbox("الفترة الزمنية:", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=3)

if stock_symbol:
    # إضافة الرمز الخاص بالبورصة المصرية في Yahoo Finance (.CA)
    full_symbol = f"{stock_symbol}.CA" if not stock_symbol.endswith(".CA") else stock_symbol

    st.subheader(f"بيانات سهم: {stock_symbol}")
    
    try:
        # جلب البيانات
        ticker = yf.Ticker(full_symbol)
        df = ticker.history(period=period)

        if not df.empty:
            # عرض آخر سعر وأعلى/أقل سعر
            last_price = df['Close'].iloc[-1]
            prev_price = df['Close'].iloc[-2] if len(df) > 1 else last_price
            change = last_price - prev_price
            pct_change = (change / prev_price) * 100

            col1, col2, col3 = st.columns(3)
            col1.metric("آخر سعر إغلاق", f"{last_price:.2f} EGP", f"{change:+.2f} ({pct_change:+.2f}%)")
            col2.metric("أعلى سعر بالفترة", f"{df['High'].max():.2f} EGP")
            col3.metric("أقل سعر بالفترة", f"{df['Low'].min():.2f} EGP")

            # رسم بياني لحركة السعر
            st.write("### رسم بياني لحركة السهم")
            st.line_chart(df['Close'])

            # جدول البيانات
            with st.expander("عرض جدول البيانات التفصيلي"):
                st.dataframe(df.sort_index(ascending=False))
        else:
            st.warning(f"لم يتم العثور على بيانات للسهم {stock_symbol}. التأكد من رمز السهم المكتوب.")
            
    except Exception as e:
        st.error(f"حدث خطأ أثناء جلب البيانات: {e}")
