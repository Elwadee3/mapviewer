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
    
    # اللون الأزرق الغامق المعتمد للأرقام والروابط
    dark_blue = "#1e3a8a"

    net.set_options("""
    {
      "physics": {
        "forceAtlas2Based": { "gravitationalConstant": -120, "springLength": 220 },
        "solver": "forceAtlas2Based", "stabilization": { "iterations": 1000 }
      },
      "nodes": { "font": { "size": 18, "face": "arial" }, "borderWidth": 2 },
      "edges": { 
        "font": { "size": 22, "align": "middle", "color": "#1e3a8a", "strokeWidth": 5, "strokeColor": "#ffffff" } 
      }
    }
    """)
    
    # 1. تكبير الدائرة الزرقاء المركزية وإظهار الكود بداخلها بشكل واضح
    net.add_node(
        selected_id, 
        label=selected_id, 
        title=html.escape(source_text), 
        color="#1687d9", 
        size=75,  # تم تكبير الحجم من 45 إلى 75
        shape="circle", 
        font={'color': 'white', 'size': 22, 'bold': True}
    )

    for idx, item in enumerate(mappings):
        edge_width = max(1, 10 - idx)
        
        # تجهيز نص الـ Tooltip النظيف والمنظم بدون كود <b> يظهر للمستخدم
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
        
        # ربط النود مع عرض الرقم عريضاً بالأزرق الغامق
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
# الواجهة الرئيسية
# -------------------------
DATA_FILE = "final_ontology_refined_mappings_with_explanations.csv"

if os.path.exists(DATA_FILE):
    df = pd.read_csv(DATA_FILE)
    df.columns = [c.strip() for c in df.columns]
    
    # 2. القائمة الجانبية تظهر العناصر تحت بعضها مباشرة باستخدام radio
    st.sidebar.title("Controls List")
    selected_id = st.sidebar.radio(
        "Select Control ID:", 
        options=df["ECC id control"].unique(),
        index=0
    )
    
    st.title("Control Mapping Viewer")
    
    row = df[df["ECC id control"].astype(str) == str(selected_id)].iloc[0]
    mappings = extract_mappings(row, df)

    # عرض الرسم البياني
    graph_html = create_graph(str(selected_id), str(row["Source Text"]), mappings)
    components.html(graph_html, height=680)

    # عرض التفسيرات في الأسفل
    st.markdown("## AI Explanations")
    
    if mappings:
        for idx, m in enumerate(mappings):
            with st.expander(f"#{idx+1} - {m['mapping']}"):
                st.markdown(f"**Commonality:** {m['commonality']}")
                st.markdown(f"**Justification:** {m['justification']}")
                st.markdown(f"**Differences:** {m['differences']}")
                st.divider()
    else:
        st.info("No mappings found for this control.")

else:
    st.error("Data file not found. Please ensure the CSV is in the same directory.")
