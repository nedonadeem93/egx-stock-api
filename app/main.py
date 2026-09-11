import sys
import os

# ضبط مسار المشروع
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
import yfinance as yf

# إعدادات الصفحة
st.set_page_config(
    page_title="محلل الأسهم المصرية - المطور",
    page_icon="📈",
    layout="wide"
)

# عنوان لوحة التحكم
st.title("📈 لوحة المتابعة وإدارة مخاطر القمم (EGX)")
st.caption("كشف القمم التاريخية، اتخاذ القرار، ونقاط الأمان - خاص بك")

# شريط جانبي لإدخال البيانات
st.sidebar.header("إعدادات البحث")
stock_symbol = st.sidebar.text_input("رمز السهم (مثال: ABUK, COMI, TMGH):", value="ABUK").upper()
period = st.sidebar.selectbox("الفترة الزمنية للتحليل:", ["6mo", "1y", "2y", "5y", "max"], index=3)

if stock_symbol:
    full_symbol = f"{stock_symbol}.CA" if not stock_symbol.endswith(".CA") else stock_symbol

    try:
        ticker = yf.Ticker(full_symbol)
        df = ticker.history(period=period)

        if not df.empty and len(df) >= 20:
            # --- حساب المؤشرات الفنية ---
            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean() if len(df) >= 50 else df['EMA20']
            df['Vol_Avg20'] = df['Volume'].rolling(window=20).mean()

            # بيانات الجلسة الأخيرة والقمة التاريخية
            last_close = df['Close'].iloc[-1]
            last_high = df['High'].iloc[-1]
            last_low = df['Low'].iloc[-1]
            last_vol = df['Volume'].iloc[-1]
            avg_vol = df['Vol_Avg20'].iloc[-1] if not pd.isna(df['Vol_Avg20'].iloc[-1]) else last_vol
            prev_close = df['Close'].iloc[-2] if len(df) > 1 else last_close

            # القمة والقاع التاريخي في الفترة المختارة
            ath_price = df['High'].max() # القمة التاريخية
            atl_price = df['Low'].min()

            # تغير السعر
            change = last_close - prev_close
            pct_change = (change / prev_close) * 100

            st.subheader(f"📊 ملخص الجلسة والقمم: {stock_symbol}")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("آخر سعر إغلاق", f"{last_close:.2f} EGP", f"{change:+.2f} ({pct_change:+.2f}%)")
            col2.metric("أعلى سعر بالجلسة", f"{last_high:.2f} EGP")
            col3.metric("🏆 القمة التاريخية (ATH)", f"{ath_price:.2f} EGP")
            col4.metric("حجم التداول", f"{last_vol:,.0f}")

            # --- حساب النقاط المحورية (Pivot Points) ---
            pivot = (last_high + last_low + last_close) / 3
            r1 = (2 * pivot) - last_low
            s1 = (2 * pivot) - last_high
            r2 = pivot + (last_high - last_low)
            s2 = pivot - (last_high - last_low)

            # وقف الخسارة
            stop_loss = s2 * 0.985

            st.markdown("---")
            st.subheader("🛡️ تقييم أمان القمم والقرار التكتيكي")

            # كشف القمة التاريخية (لو السعر قريب جداً من القمة بفرق 2% مثلاً)
            is_near_ath = (last_close >= ath_price * 0.97) and (last_close <= ath_price * 1.01)

            if is_near_ath:
                st.error(f"⚠️ **تحذير شديد: السهم عند قمة تاريخية (سعر {last_close:.2f} قريب من {ath_price:.2f})!**")
                st.write(f"🛑 **ممنوع الشراء بأسعار السوق الآن.** السهم معرض لارتداد وهبوط لأسفل (قد يستهدف مناطق الـ 90 أو أقل لتجميع السيولة).")
                st.write(f"✅ **الشرط الوحيد للشراء:** إغلاق مؤكد فوق `{ath_price:.2f}` بتداول قوي، أو الانتظار حتى الهبوط لمناطق الدعم.")
            elif last_close < s1:
                st.success("🟢 **السهم في منطقة تصحيح ودعم ممتازة للشراء.**")
            else:
                st.info("🔵 **السهم في منطقة حركة متوازنة.**")

            # تفاصيل خطة العمل
            st.markdown("### 📋 أسعار ومناطق التنفيذ المقترحة:")
            c1, c2, c3 = st.columns(3)
            
            with c1:
                st.markdown(f"**📉 الشراء الآمن (بعد التصحيح):**\n`{s2:.2f}` إلى `{s1:.2f}` جنيه\n*(المناطق المتوقعة لو نزل عن 94)*")
            with c2:
                st.markdown(f"**🚀 شرط شراء الاختراق:**\nإغلاق مؤكد فوق `{ath_price:.2f}` جنيه")
            with c3:
                st.markdown(f"**🛑 وقف الخسارة صارم:**\n`{stop_loss:.2f}` جنيه")

            # --- الرسم البياني ---
            st.markdown("---")
            st.write("### 📉 حركة السهم مقارنة بالقمة التاريخية")
            st.line_chart(df['Close'])

            with st.expander("عرض جدول البيانات التفصيلي"):
                st.dataframe(df.sort_index(ascending=False))

        else:
            st.warning("البيانات المتاحة غير كافية للتحليل.")
            
    except Exception as e:
        st.error(f"حدث خطأ أثناء جلب البيانات: {e}")
