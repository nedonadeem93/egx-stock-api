import sys
import os

# ضبط مسار المشروع
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
import yfinance as yf

# إعدادات الصفحة
st.set_page_config(
    page_title="محلل الأسهم المصرية - الذكي",
    page_icon="📈",
    layout="wide"
)

# عنوان لوحة التحكم
st.title("📈 لوحة المتابعة والتحليل الفني الذكي (EGX)")
st.caption("تقييم الأمان، الاتجاه، مستويات الدعم، ووقف الخسارة - خاص بك")

# شريط جانبي لإدخال البيانات
st.sidebar.header("إعدادات البحث")
stock_symbol = st.sidebar.text_input("رمز السهم (مثال: COMI, TMGH, FWRY, ABUK):", value="COMI").upper()
period = st.sidebar.selectbox("الفترة الزمنية للتحليل:", ["3mo", "6mo", "1y", "2y"], index=1)

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

            # بيانات الجلسة الأخيرة
            last_close = df['Close'].iloc[-1]
            last_high = df['High'].iloc[-1]
            last_low = df['Low'].iloc[-1]
            last_vol = df['Volume'].iloc[-1]
            avg_vol = df['Vol_Avg20'].iloc[-1] if not pd.isna(df['Vol_Avg20'].iloc[-1]) else last_vol
            prev_close = df['Close'].iloc[-2] if len(df) > 1 else last_close

            # تغير السعر
            change = last_close - prev_close
            pct_change = (change / prev_close) * 100

            st.subheader(f"📊 ملخص الجلسة الأخيرة: {stock_symbol}")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("آخر سعر إغلاق", f"{last_close:.2f} EGP", f"{change:+.2f} ({pct_change:+.2f}%)")
            col2.metric("أعلى سعر للجلسة", f"{last_high:.2f} EGP")
            col3.metric("أقل سعر للجلسة", f"{last_low:.2f} EGP")
            col4.metric("حجم التداول", f"{last_vol:,.0f}", f"{((last_vol - avg_vol)/avg_vol)*100:+.1f}% vs المتوسط")

            # --- حساب النقاط المحورية (Pivot Points) ---
            pivot = (last_high + last_low + last_close) / 3
            r1 = (2 * pivot) - last_low
            s1 = (2 * pivot) - last_high
            r2 = pivot + (last_high - last_low)
            s2 = pivot - (last_high - last_low)

            # --- تقييم الاتجاه وحجم التداول ---
            is_uptrend = (last_close > df['EMA20'].iloc[-1]) and (df['EMA20'].iloc[-1] > df['EMA50'].iloc[-1])
            is_downtrend = (last_close < df['EMA20'].iloc[-1]) and (df['EMA20'].iloc[-1] < df['EMA50'].iloc[-1])
            high_volume = last_vol > (avg_vol * 1.2)

            # وقف الخسارة الموصى به (أسفل S2 بـ 1.5%)
            stop_loss = s2 * 0.985

            st.markdown("---")
            st.subheader("🛡️ تقييم درجة الأمان والخطة التكتيكية للشراء")

            # صياغة التوصية المدمجة بناءً على 3 عوامل
            if is_downtrend:
                st.error("❌ **درجة الأمان: منخفضة (اتجاه هابط صريح)**")
                st.write(f"السهم يتحرك تحت المتوسطات المتحركة الرئيسيّة. **الشراء الآن فيه مخاطرة عالية** حتي لو كان السعر عند الدعم. يفضل الانتظار لتأكيد ارتداد السهم فوق مستوى **{s1:.2f} EGP**.")
            elif is_uptrend and (last_close <= s1 * 1.02):
                st.success("✅ **درجة الأمان: عالية جداً (فرصة شراء نموذجية)**")
                st.write(f"السهم في اتجاه صاعد عام وبدأ بالاقتراب من مناطق الدعم القوية. الشراء آمن ومناسب جداً في الوقت الحالي.")
            elif last_close >= r1:
                st.warning("⚠️ **درجة الأمان: متوسطة/منخفضة (السعر قريب من المقاومة)**")
                st.write(f"السهم قريب من مناطق جني الأرباح (**{r1:.2f} EGP**). يُفضّل عدم الدخول بأسعار مرتفعة وانتظار تهدئة السعر للاقتراب من مناطق الدعم.")
            else:
                st.info("🔵 **درجة الأمان: متوسطة (سعر متوازن)**")
                st.write(f"السهم يتحرك في نطاق عرضي حول النقطة المحورية. يُنصح بالدخول الجزئي (على دفعات).")

            # تفاصيل النطاقات
            st.markdown("### 📋 النطاقات الرقمية وخطّة التنفيذ:")
            c_buy, c_stop, c_target = st.columns(3)
            
            with c_buy:
                st.markdown(f"**🟢 نطاق الشراء الآمن (التجميع):**\n`{s2:.2f}` إلى `{s1:.2f}` جنيه")
            with c_stop:
                st.markdown(f"**🛑 حد وقف الخسارة (Stop Loss):**\n`{stop_loss:.2f}` جنيه *(إغلاق يومي أسفل هذا السعر)*")
            with c_target:
                st.markdown(f"**🎯 هدف المقاومة والأرباح:**\n`{r1:.2f}` إلى `{r2:.2f}` جنيه")

            # --- الرسم البياني مع المتوسطات المتحركة ---
            st.markdown("---")
            st.write("### 📉 الرسم البياني مع اتجاه المتوسطات المتحركة (EMA 20 & 50)")
            st.line_chart(df[['Close', 'EMA20', 'EMA50']])

            with st.expander("عرض جدول البيانات التفصيلي"):
                st.dataframe(df.sort_index(ascending=False))

        else:
            st.warning("البيانات المتاحة للسهم غير كافية لإجراء التحليل الفني بشكل صحيح.")
            
    except Exception as e:
        st.error(f"حدث خطأ أثناء جلب البيانات: {e}")
