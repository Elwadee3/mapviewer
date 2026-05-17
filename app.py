import streamlit as st
import pandas as pd
from pyvis.network import Network
import streamlit.components.v1 as components
import tempfile
import html
import os

# إعداد الصفحة
st.set_page_config(page_title="Control Mapping Viewer", layout="wide")

# -------------------------
# تحسين المظهر باستخدام CSS (البطاقات الجانبية وصندوق البحث)
# -------------------------
st.markdown("""
<style>
    /* تخصيص صندوق البحث */
    div[data-testid="stSidebar"] .stTextInput input {
        border-radius: 6px;
        border: 1px solid #cbd5e1;
        padding: 8px;
    }
    
    /* تصميم البطاقات الجانبية */
    .control-card {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 12px;
        background-color: #ffffff;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        cursor: pointer;
        transition: transform 0.2s, border-color 0.2s;
    }
    .control-card:hover {
        border-color: #1687d9;
        transform: translateY(-2px);
    }
    .control-card-active {
        border: 2px solid #1687d9;
        background-color: #f0fdf4;
    }
    .card-id {
        font-weight: bold;
        color: #334155;
        font-size: 15px;
        margin-bottom: 4px;
    }
    .card-text {
        font-size: 13px;
        color: #64748b;
        line-height: 1.4;
        margin-bottom: 6px;
    }
    .card-footer {
        font-size: 12px;
        color: #475569;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------
# وظائف معالجة البيانات
# -------------------------
def get_mapping_columns(i):
    suffix = "" if i == 1 else f" {i}"
    return {
        "mapping": f"NIST mapping{suffix}",
        "text": f"Text{suffix}",
        "final": f"Final Score{suffix}",
        "commonality": f"Commonality{suffix}",
        "justification": f"Justification{suffix}",
        "differences": f"Differences{suffix}"
    }

def extract_mappings(row, df, top_k=10):
    results = []
    for i in range(1, 11):
        cols = get_mapping_columns(i)
        if cols["mapping"] not in df.columns or pd.isna(row.get(cols["mapping"])):
            continue
        try:
            val = str(row.get(cols["final"], 0)).replace('%', '')
            score = float(val) / 100.0 if float(val) > 1.0 else float(val)
        except:
            score = 0.0
        
        commonality_val = row.get(cols["commonality"], "")
        justification_val = row.get(cols["justification"], "")
        differences_val = row.get(cols["differences"], "")
        
        if pd.isna(differences_val) or differences_val == "":
            differences_val = "The controls differ in implementation focus and specific requirements."
        
        results.append({
            "rank": i,
            "mapping": str(row.get(cols["mapping"], "")),
            "text": str(row.get(cols["text"], "")),
            "final": score,
            "commonality": str(commonality_val) if not pd.isna(commonality_val) else "N/A",
            "justification": str(justification_val) if not pd.isna(justification_val) else "N/A",
            "differences": str(differences_val)
        })
    return sorted(results, key=lambda x: x["final"], reverse=True)[:top_k]

def create_graph(selected_id, source_text, mappings):
    net = Network(height="650px", width="100%", bgcolor="#ffffff")
    dark_blue = "#1e3a8a"

    net.set_options("""
    {
      "physics": {
        "forceAtlas2Based": { "gravitationalConstant": -150, "springLength": 240 },
        "solver": "forceAtlas2Based", "stabilization": { "iterations": 1000 }
      },
      "nodes": { "font": { "size": 18, "face": "arial" }, "borderWidth": 2 },
      "edges": { 
        "font": { "size": 22, "align": "middle", "color": "#1e3a8a", "strokeWidth": 5, "strokeColor": "#ffffff" } 
      }
    }
    """)
    
    # تكبير الدائرة الزرقاء المركزية بشكل ملحوظ وضبط حجم الخط بداخلها
    net.add_node(
        selected_id, 
        label=selected_id, 
        title=html.escape(source_text), 
        color="#1687d9", 
        size=110,  # تم تكبير الحجم مرة أخرى إلى 110 بناءً على طلبك
        shape="circle", 
        font={'color': 'white', 'size': 28, 'bold': True}
    )

    for idx, item in enumerate(mappings):
        edge_width = max(1, 10 - idx)
        
        hover_info = (
            f"Mapping: {item['mapping']}\n"
            f"Commonality: {item['commonality']}\n"
            f"Justification: {item['justification']}\n"
            f"Differences: {item['differences']}"
        )
        
        net.add_node(
            item["mapping"], 
            label=item["mapping"], 
            title=html.escape(item["text"]), 
            color="#328a36", 
            size=35, 
            shape="circle", 
            font={'color': 'white', 'size': 16}
        )
        
        net.add_edge(
            selected_id, 
            item["mapping"], 
            label=f" #{idx+1} ", 
            title=hover_info, 
            width=edge_width,
            color={"color": "#cbd5e1", "highlight": dark_blue}
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
        net.save_graph(tmp.name)
        return open(tmp.name, 'r', encoding='utf-8').read()

# -------------------------
# الواجهة الرئيسية وتصميم القائمة الجانبية المتقدم
# -------------------------
DATA_FILE = "final_ontology_refined_mappings_with_explanations.csv"

if os.path.exists(DATA_FILE):
    df = pd.read_csv(DATA_FILE)
    df.columns = [c.strip() for c in df.columns]
    
    # شريط البحث الجانبي والبطاقات
    st.sidebar.title("Controls List")
    search_query = st.sidebar.text_input("Search by control number (e.g., 2.4)", placeholder="Type
