import streamlit as st
import pandas as pd
from pyvis.network import Network
import streamlit.components.v1 as components
import tempfile
import html
import os

# إعداد الصفحة
st.set_page_config(
    page_title="Control Mapping Viewer", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------
# تحسين المظهر باستخدام CSS المطور للبطاقات القابلة للضغط مباشرة
# -------------------------
st.markdown("""
<style>
    /* تخصيص صندوق البحث الجانبي */
    div[data-testid="stSidebar"] .stTextInput input {
        border-radius: 6px;
        border: 1px solid #cbd5e1;
        padding: 8px;
    }
    
    /* إلغاء الهوامش المزعجة لأزرار المكونات الشفافة */
    div[data-testid="stSidebar"] div.stButton > button {
        border: none !important;
        background: transparent !important;
        padding: 0 !important;
        margin: 0 !important;
        height: auto !important;
        width: 100% !important;
        text-align: left !important;
        box-shadow: none !important;
    }
    div[data-testid="stSidebar"] div.stButton > button:hover {
        background: transparent !important;
        border: none !important;
    }
    div[data-testid="stSidebar"] div.stButton > button:active {
        background: transparent !important;
        border: none !important;
    }
    
    /* تصميم مظهر البطاقات الجانبية */
    .control-card {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 14px;
        margin-bottom: 12px;
        background-color: #ffffff;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        transition: border-color 0.2s, background-color 0.2s;
        width: 100%;
        box-sizing: border-box;
    }
    .control-card:hover {
        border-color: #1687d9;
        background-color: #f8fafc;
    }
    .control-card-active {
        border: 2px solid #1687d9;
        background-color: #f0fdf4;
    }
    .card-id {
        font-weight: bold;
        color: #1e293b;
        font-size: 16px;
        margin-bottom: 4px;
    }
    .card-text {
        font-size: 13px;
        color: #64748b;
        line-height: 1.4;
        margin-bottom: 6px;
        white-space: normal;
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
        "forceAtlas2Based": { "gravitationalConstant": -180, "springLength": 260 },
        "solver": "forceAtlas2Based", "stabilization": { "iterations": 1000 }
      },
      "nodes": { "font": { "size": 18, "face": "arial" }, "borderWidth": 2 },
      "edges": { 
        "font": { "size": 22, "align": "middle", "color": "#1e3a8a", "strokeWidth": 5, "strokeColor": "#ffffff" } 
      }
    }
    """)
    
    # ضبط الدائرة المركزية الزرقاء بشكل ضخم وبارز
    net.add_node(
        selected_id, 
        label=selected_id, 
        title=html.escape(source_text), 
        color="#1687d9", 
        size=1000, 
        shape="circle", 
        font={'color': 'white', 'size': 40, 'bold': True}
    )

    for idx, item in enumerate(mappings):
        edge_width = max(1, 10 - idx)
        
        # صياغة الـ Tooltip المنبثق ليكون نظيفاً ومقروءاً بدون وسوم داخلية
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
    
    unique_controls = df["ECC id control"].dropna().unique()
    if search_query:
        filtered_controls = [c for c in unique_controls if search_query.strip() in str(c)]
    else:
        filtered_controls = list(unique_controls)
    
    st.sidebar.markdown("### Controls")
    
    # إدارة تهيئة وتحديث العنصر النشط في الواجهة
    if "selected_control_id" not in st.session_state and len(filtered_controls) > 0:
        st.session_state.selected_control_id = str(filtered_controls[0])
    elif len(filtered_controls) > 0 and st.session_state.selected_control_id not in [str(c) for c in filtered_controls]:
        st.session_state.selected_control_id = str(filtered_controls[0])

    if filtered_controls:
        for ctrl_id in filtered_controls:
            str_ctrl_id = str(ctrl_id)
            ctrl_row = df[df["ECC id control"].astype(str) == str_ctrl_id].iloc[0]
            ctrl_text = str(ctrl_row.get("Source Text", ""))
            short_text = ctrl_text if len(ctrl_text) < 120 else ctrl_text[:120] + "..."
            
            is_active = (str_ctrl_id == str(st.session_state.selected_control_id))
            card_class = "control-card control-card-active" if is_active else "control-card"
            
            with st.sidebar:
                # لتفادي التكرار وجعل مساحة الزر الشفاف تغطي كامل مساحة البطاقة
                if st.button(label="", key=f"btn_nav_{str_ctrl_id}"):
                    st.session_state.selected_control_id = str_ctrl_id
                    st.rerun()
                
                # طباعة المظهر الفعلي للبطاقة ليتلقى المظهر النشط
                st.markdown(f"""
                <div class="{card_class}" style="margin-top: -25px; pointer-events: none; position: relative; z-index: 1;">
                    <div class="card-id">{str_ctrl_id}</div>
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

        # توليد وعرض الرسم البياني
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
