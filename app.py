import streamlit as st
import pandas as pd
from pyvis.network import Network
import streamlit.components.v1 as components
import tempfile
import html
import os

st.set_page_config(
    page_title="Control Mapping Viewer",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------
# CSS STYLE 
# -------------------------
st.markdown("""
<style>
body { background-color: #f5f5f5; }
.block-container { padding-top: 2rem; padding-left: 2rem; padding-right: 1rem; }
[data-testid="stSidebar"] { min-width: 430px; max-width: 430px; background-color: #ffffff; border-right: 1px solid #ddd; }
.main-title { font-size: 48px; font-weight: 800; color: #2f2f2f; margin-bottom: 10px; }
.subtitle { font-size: 20px; color: #111827; margin-top: -8px; margin-bottom: 20px; }
.sidebar-title { font-size: 22px; font-weight: 800; color: #1f2937; margin-bottom: 12px; }
.mapping-card { border: 2px solid #1e3a8a; border-radius: 6px; background-color: #f8fafc; padding: 14px; margin-bottom: 14px; }
.mapping-title { font-size: 18px; font-weight: 800; color: #1e3a8a; }
.rank-pill { background-color: #1e3a8a; color: white; border-radius: 18px; padding: 3px 10px; font-weight: 700; margin-right: 10px; }
.mapping-text { color: #475569; font-size: 14px; line-height: 1.5; margin-top: 8px; }
.graph-box { border: 1px solid #d8d8d8; background-color: white; border-radius: 5px; }

/* Sidebar Button Styles */
[data-testid="stSidebar"] div.stButton > button {
    width: 100%; height: auto; text-align: left; padding: 14px; 
    border-radius: 6px; border: 1px solid #e5e5e5; background-color: #ffffff;
    color: #444; margin-bottom: 8px; display: block; white-space: normal;
}
[data-testid="stSidebar"] div.stButton > button:hover {
    background-color: #eaf6ff; border: 1px solid #1476d4; color: #1476d4;
}
.selected-control-card button { background-color: #dff0ff !important; border: 2px solid #1476d4 !important; }
</style>
""", unsafe_allow_html=True)

# -------------------------
# HELPERS 
# -------------------------
def short_text(text, limit=150):
    text = str(text)
    return text if len(text) <= limit else text[:limit] + "..."

def get_mapping_columns(i):
    if i == 1:
        return {
            "mapping": "NIST mapping", "text": "Text", "dense": "Dense",
            "sparse": "Sparse", "hybrid": "Hybrid", "ontology": "Ontology Score",
            "final": "Final Score", "confidence": "Confidence match"
        }
    return {
        "mapping": f"NIST mapping {i}", "text": f"Text {i}", "dense": f"Dense {i}",
        "sparse": f"Sparse {i}", "hybrid": f"Hybrid {i}", "ontology": f"Ontology Score {i}",
        "final": f"Final Score {i}", "confidence": f"Confidence match {i}"
    }

def extract_mappings(row, df, top_k):
    results = []
    for i in range(1, 11):
        cols = get_mapping_columns(i)
        if cols["mapping"] not in df.columns or pd.isna(row.get(cols["mapping"])):
            continue
        results.append({
            "rank": i,
            "mapping": str(row.get(cols["mapping"], "")),
            "text": str(row.get(cols["text"], "")),
            "dense": float(row.get(cols["dense"], 0)),
            "final": float(row.get(cols["final"], 0)),
            "confidence": str(row.get(cols["confidence"], ""))
        })
    return sorted(results, key=lambda x: x["final"], reverse=True)[:top_k]

def create_graph(selected_control, source_text, mappings):
    net = Network(height="580px", width="100%", bgcolor="#ffffff", directed=False)
    
    # لون أزرق غامق ملكي للأرقام
    deep_blue = "#1e3a8a" 
    
    net.set_options("""
    {
      "nodes": { "borderWidth": 2, "font": { "size": 18, "color": "white" } },
      "edges": { "smooth": false, "font": { "strokeWidth": 5, "strokeColor": "#ffffff" } },
      "physics": { "enabled": true, "solver": "repulsion", "repulsion": { "nodeDistance": 200 } }
    }
    """)

    # نود مركزية (ECC)
    net.add_node(selected_control, label=selected_control, color="#1687d9", size=100, font={"size": 40, "bold": True})

    for item in mappings:
        score_percent = item["final"] * 100
        net.add_node(item["mapping"], label=item["mapping"], color="#328a36", size=30)
        
        net.add_edge(
            selected_control, item["mapping"],
            label=f" #{item['rank']} ",
            title=f"Score: {score_percent:.0f}%",
            width=5 if item["rank"] <= 3 else 2,
            color={"color": "#cbd5e1", "highlight": deep_blue},
            font={"color": deep_blue, "size": 30, "bold": True} # تعديل لون وحجم الرقم
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
        net.save_graph(tmp.name)
        with open(tmp.name, "r", encoding="utf-8") as f:
            return f.read()

# -------------------------
# DATA LOADING
# -------------------------
DATA_PATH = "final_ontology_refined_mappings_with_explanations.csv"
if os.path.exists(DATA_PATH):
    df = pd.read_csv(DATA_PATH)
else:
    uploaded_file = st.file_uploader("Upload CSV:", type=["csv"])
    if uploaded_file: df = pd.read_csv(uploaded_file)
    else: st.stop()

control_col, source_col = "ECC id control", "Source Text"
controls_df = df[[control_col, source_col]].dropna().copy()
controls_df[control_col] = controls_df[control_col].astype(str)

# -------------------------
# SIDEBAR
# -------------------------
st.sidebar.markdown('<div class="sidebar-title">Controls</div>', unsafe_allow_html=True)
search = st.sidebar.text_input("", placeholder="Search...")
if search:
    controls_df = controls_df[controls_df[control_col].str.contains(search, case=False)]

if "selected_control" not in st.session_state:
    st.session_state.selected_control = controls_df[control_col].iloc[0]

with st.sidebar.container(height=500):
    for _, r in controls_df.iterrows():
        cid = str(r[control_col])
        if st.button(f"{cid}: {short_text(r[source_col], 50)}", key=f"btn_{cid}"):
            st.session_state.selected_control = cid
            st.rerun()

# -------------------------
# MAIN UI
# -------------------------
selected_control = st.session_state.selected_control
row = df[df[control_col].astype(str) == selected_control].iloc[0]
mappings = extract_mappings(row, df, 10)

st.markdown('<div class="main-title">Control Mapping Viewer</div>', unsafe_allow_html=True)
st.markdown(f'<div class="subtitle">Selected: {selected_control}</div>', unsafe_allow_html=True)

col_left
