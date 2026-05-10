import streamlit as st
import pandas as pd
import os
import re
from groq import Groq
from pyvis.network import Network
import streamlit.components.v1 as components

# إعداد الصفحة
st.set_page_config(page_title="Control Mapping Viewer", layout="wide", initial_sidebar_state="expanded")

# --- إدارة مفتاح الـ API بشكل آمن ---
try:
    # سيحاول الكود القراءة من Secrets الخاصة بـ Streamlit أولاً
    api_key = st.secrets["GROQ_API_KEY"]
except Exception:
    # إذا لم يجدها (مثلاً عند التشغيل المحلي) سيحاول القراءة من البيئة
    api_key = os.getenv("GROQ_API_KEY", "")

# تعريف العميل (Client) فقط إذا وجد المفتاح لتجنب خطأ التوقف المفاجئ
client = None
if api_key:
    client = Groq(api_key=api_key)

# --- دالة تحميل البيانات المصححة ---
def load_data():
    base_path = os.path.dirname(__file__)
    # تأكد أن اسم الملف يطابق ما هو مرفوع في مجلد data
    file_path = os.path.join(base_path, "final_ontology_refined_mappings_with_explanations.csv")
    
    if os.path.exists(file_path):
        return pd.read_csv(file_path)
    else:
        st.error(f"❌ ملف البيانات غير موجود في: {file_path}")
        return None

# تشغيل التطبيق الرئيسي
df = load_data()

if df is not None:
    st.title("📊 Control Mapping Viewer")
    st.info("تم تحميل البيانات بنجاح. استخدم القائمة الجانبية للتنقل.")
    
    # هنا تضع بقية منطق العرض الخاص بك (الشبكة، البطاقات، إلخ)
    # مع التأكد من بقاء الإزاحة (Indentation) صحيحة تحت كل دالة أو شرط
