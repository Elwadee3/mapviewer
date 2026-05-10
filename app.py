import pandas as pd
import os
import re
import time
from dotenv import load_dotenv
from groq import Groq
from tqdm import tqdm

# ==========================================
# 1. إعدادات البيئة والاتصال
# ==========================================
# تأكد من وجود ملف .env يحتوي على GROQ_API_KEY
load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    print("خطأ كببر: لم يتم العثور على مفتاح GROQ_API_KEY في ملف .env")
    exit()

client = Groq(api_key=api_key)

# ==========================================
# 2. وظائف التصفية والتنظيف الذكية
# ==========================================
def remove_parent_controls(df):
    """
    الإبقاء فقط على الضوابط التفصيلية (مثلاً 1.1.1) واستبعاد الرئيسية (1.1).
    هذا يضمن أن عملية الربط تتم على أدق مستوى من البيانات.
    """
    return df[df["ECC id control"].astype(str).str.count(r"\.") >= 2].copy()

def clean_ai_output(text):
    """تنظيف النصوص المولدة من أي حشو برمجي أو وسوم زائدة لضمان مظهر نظيف في الموقع."""
    if not isinstance(text, str): return ""
    tags = ["Commonality:", "Justification:", "Differences:"]
    for tag in tags:
        text = text.replace(tag, "")
    return re.sub(r"\s+", " ", text).strip()

# ==========================================
# 3. محرك الاستدلال (AI Inference Engine) مع نظام Caching
# ==========================================
# ذاكرة مؤقتة لتوفير استهلاك الـ API ومنع تكرار معالجة نصوص NIST المتطابقة
cache = {}

def generate_text(ecc_text, nist_text):
    cache_key = hash(nist_text)
    if cache_key in cache:
        return cache[cache_key]

    prompt = f"""
You are a cybersecurity ontology expert. Compare these two controls:

ECC Control:
{ecc_text}

NIST Control:
{nist_text}

Provide exactly three points (maximum 2 sentences each):
1. Commonality: What do they share?
2. Justification: Why is this mapping technically correct?
3. Differences: How does their focus or implementation vary?

Rules:
- Professional tone.
- Do not mention scores or percentages.
- Be concise.
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2, # درجة حرارة منخفضة لضمان استقرار الإجابات التقنية
        )
        
        output = response.choices[0].message.content.strip()
        lines = output.split("\n")
        
        results = ["", "", ""]
        keys = ["Commonality:", "Justification:", "Differences:"]
        
        for line in lines:
            for idx, key in enumerate(keys):
                if line.strip().startswith(key):
                    results[idx] = clean_ai_output(line)
        
        cache[cache_key] = tuple(results)
        return results
    except Exception as e:
        print(f"API Error: {e}")
        # رد احتياطي في حال فشل الاتصال لضمان عدم توقف الكود
        return ("Both controls share related cybersecurity objectives.", 
                "Technical mapping based on shared security domains.", 
                "Focus areas and implementation wording vary.")

# ==========================================
# 4. المعالجة الرئيسية (Batch Processing)
# ==========================================
def run():
    # تأكد من صحة مسارات الملفات في مجلد مشروعك
    input_file = "final_ontology_refined_mappings_with_explanations.csv"
