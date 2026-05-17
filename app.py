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
# تحسين المظهر باستخدام CSS المطور للبطاقات القابلة للضغط مباشرة
# -------------------------
st.markdown("""
<style>
body {
    background-color: #f5f5f5;
}

.block-container {
    padding-top: 2rem;
    padding-left: 2rem;
    padding-right: 1rem;
}

[data-testid="stSidebar"] {
    min-width: 430px;
    max-width: 430px;
}

div[data-baseweb="select"] {
    font-size: 14px;
}

[data-testid="stSidebar"] {
    background-color: #ffffff;
    border-right: 1px solid #ddd;
}

.main-title {
    font-size: 64px;
    font-weight: 800;
    color: #2f2f2f;
    margin-bottom: 0;
}

.subtitle {
    font-size: 22px;
    color: #111827;
    margin-top: -8px;
}

.sidebar-title {
    font-size: 22px;
    font-weight: 800;
    color: #1f2937;
    margin-bottom: 12px;
}

.control-card {
    padding: 18px;
    border-radius: 0px;
    border-bottom: 1px solid #eee;
    cursor: pointer;
}

.control-card-selected {
    background-color: #dff0ff;
    padding: 18px;
    border-radius: 0px;
    border-bottom: 1px solid #eee;
}

.control-id {
    font-size: 24px;
    font-weight: 800;
    color: #1476d4;
}

.control-text {
    font-size: 18px;
    color: #666;
    line-height: 1.35;
}

.small-muted {
    color: #8a8a8a;
    font-size: 16px;
}

.mapping-card {
    border: 2px solid #75b843;
    border-radius: 6px;
    background-color: #f1faec;
    padding: 14px;
    margin-bottom: 14px;
}

.mapping-title {
    font-size: 20px;
    font-weight: 800;
    color: #1476d4;
}

.rank-pill {
    background-color: #1476d4;
    color: white;
    border-radius: 18px;
    padding: 5px 10px;
    font-weight: 700;
    margin-right: 10px;
}

.score-line {
    float: right;
    font-size: 14px;
    font-weight: 800;
}

.score-green {
    color: #00a13a;
}

.score-purple {
    color: #7b2cff;
}

.score-blue {
    color: #005cff;
}

.mapping-text {
    clear: both;
    color: #555;
    font-size: 15px;
    line-height: 1.5;
    margin-top: 12px;
}

.graph-box {
    border: 1px solid #d8d8d8;
    background-color: white;
    border-radius: 5px;
    padding: 0px;
}

div.stButton > button {
    width: 100%;
    text-align: left;
    border-radius: 0;
    border: none;
    background-color: white;
    color: #444;
    padding: 16px;
}

div.stButton > button:hover {
    background-color: #dff0ff;
    color: #1476d4;
}
</style>
""", unsafe_allow_html=True)

# -------------------------
# HELPERS 
# -------------------------
def short_text(text, limit=150):
    text = str(text)
    return text if len(text) <= limit else text[:limit] + "..."

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
        "forceAtlas2Based": { "gravitationalConstant": -180, "springLength": 260 },
        "solver": "forceAtlas2Based", "stabilization": { "iterations": 1000 }
      },
      "nodes": { "font": { "size": 18, "face": "arial" }, "borderWidth": 2 },
      "edges": { 
        "font": { "size": 22, "align": "middle", "color": "#1e3a8a", "strokeWidth": 5, "strokeColor": "#ffffff" } 
      }
    }
    """)
    
    # تكبير الدائرة المركزية الزرقاء بشكل ضخم وبارز جداً وضبط أبعاد الخط بداخلها
    net.add_node(
        selected_id, 
        label=selected_id, 
        title=html.escape(source_text), 
        color="#1687d9", 
        size=160,  # تم التكبير بشكل ملحوظ بناءً على طلبك لتبدو ضخمة ومتناسقة
        shape="circle", 
        font={'color': 'white', 'size': 32, 'bold': True}
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
    
    st.sidebar.title("Controls List")
    search_query = st.sidebar.text_input("Search by control number (e.g., 2.4)", placeholder="Type to filter...")
    
    unique_controls = df["ECC id control"].unique()
    if search_query:
        filtered_controls = [c for c in unique_controls if search_query.strip() in str(c)]
    else:
        filtered_controls = list(unique_controls)
    
    st.sidebar.markdown("### Controls")
    
    # إدارة تهيئة وتحديث العنصر النشط في الواجهة
    if "selected_control_id" not in st.session_state and len(filtered_controls) > 0:
        st.session_state.selected_control_id = filtered_controls[0]
    elif len(filtered_controls) > 0 and st.session_state.selected_control_id not in filtered_controls:
        st.session_state.selected_control_id = filtered_controls[0]

    if filtered_controls:
        for ctrl_id in filtered_controls:
            ctrl_row = df[df["ECC id control"].astype(str) == str(ctrl_id)].iloc[0]
            ctrl_text = str(ctrl_row.get("Source Text", ""))
            short_text = ctrl_text if len(ctrl_text) < 120 else ctrl_text[:120] + "..."
            
            is_active = (str(ctrl_id) == str(st.session_state.selected_control_id))
            card_class = "control-card control-card-active" if is_active else "control-card"
            
            # حيلة هندسية ذكية: نغلف البطاقة بالكامل داخل زر شفاف ممتد العرض 
            # ليتم التقاط النقرة على البطاقة الجانبية مباشرة دون الحاجة لزر مخصص
            with st.sidebar:
                if st.button(label=f"hidden_click_{ctrl_id}", key=f"btn_{ctrl_id}"):
                    st.session_state.selected_control_id = ctrl_id
                    st.rerun()
                
                # طباعة المظهر الفعلي للبطاقة ليتلقى المظهر النشط
                st.markdown(f"""
                <div class="{card_class}" style="margin-top: -38px; pointer-events: none;">
                    <div class="card-id">{ctrl_id}</div>
                    <div class="card-text">{short_text}</div>
                    <div class="card-footer">10 recommended mappings</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.sidebar.info("No matching controls found.")
    
    if "selected_control_id" in st.session_state and len(filtered_controls) > 0:
        selected_id = st.session_state.selected_control_id
        st.title("Control Mapping Viewer")
        
        row = df[df["ECC id control"].astype(str) == str(selected_id)].iloc[0]
        mappings = extract_mappings(row, df)

        # توليد وعرض الرسم البياني مع الدائرة الكبيرة الجديدة
        graph_html = create_graph(str(selected_id), str(row["Source Text"]), mappings)
        components.html(graph_html, height=680)

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
