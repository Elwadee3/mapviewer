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


def get_mapping_columns(i):
    if i == 1:
        return {
            "mapping": "NIST mapping",
            "text": "Text",
            "dense": "Dense",
            "sparse": "Sparse",
            "hybrid": "Hybrid",
            "ontology": "Ontology Score",
            "final": "Final Score",
            "confidence": "Confidence match"
        }
    return {
        "mapping": f"NIST mapping {i}",
        "text": f"Text {i}",
        "dense": f"Dense {i}",
        "sparse": f"Sparse {i}",
        "hybrid": f"Hybrid {i}",
        "ontology": f"Ontology Score {i}",
        "final": f"Final Score {i}",
        "confidence": f"Confidence match {i}"
    }


def extract_mappings(row, df, top_k):
    results = []

    for i in range(1, 11):
        cols = get_mapping_columns(i)

        if cols["mapping"] not in df.columns:
            continue

        if pd.isna(row.get(cols["mapping"])):
            continue

        final_score = float(row.get(cols["final"], 0))
        dense = float(row.get(cols["dense"], 0))
        sparse = float(row.get(cols["sparse"], 0))
        hybrid = float(row.get(cols["hybrid"], 0))

        results.append({
            "rank": i,
            "mapping": str(row.get(cols["mapping"], "")),
            "text": str(row.get(cols["text"], "")),
            "dense": dense,
            "sparse": sparse,
            "hybrid": hybrid,
            "ontology": row.get(cols["ontology"], ""),
            "final": final_score,
            "confidence": str(row.get(cols["confidence"], ""))
        })

    results = sorted(results, key=lambda x: x["final"], reverse=True)
    return results[:top_k]


def create_graph(selected_control, source_text, mappings):
    net = Network(
        height="580px",
        width="100%",
        bgcolor="#ffffff",
        directed=False
    )

    net.set_options("""
    {
      "nodes": {
        "borderWidth": 2,
        "borderWidthSelected": 4,
        "font": {
          "size": 18,
          "face": "arial",
          "color": "white",
          "strokeWidth": 0
        }
      },
        "edges": {
        "color": {
            "color": "#bdbdbd",
            "highlight": "#19a34a"
        },
        "smooth": false,

        "font": {
            "size": 16,
            "face": "arial",
            "strokeWidth": 3,
            "strokeColor": "#ffffff"
        },

        "scaling": {
            "label": {
            "enabled": false
            }
        }
        },
      "physics": {
        "enabled": true,
        "solver": "repulsion",
        "repulsion": {
          "nodeDistance": 180,
          "centralGravity": 0.18,
          "springLength": 160,
          "springConstant": 0.04,
          "damping": 0.09
        },
        "stabilization": {
          "enabled": true,
          "iterations": 200
        }
      }
    }
    """)

    net.add_node(
        selected_control,
        label=selected_control,
        title=html.escape(source_text),
        color={
            "background": "#1687d9",
            "border": "#0b4f8a"
        },
        font={
            "color": "#ffffff",
            "size": 50,
            "face": "arial",
            "bold": True
        },
        shape="circle",
        size=150
    )

    for item in mappings:
        score_percent = item["final"] * 100

        net.add_node(
            item["mapping"],
            label=item["mapping"],
            title=html.escape(item["text"]),
            color={
                "background": "#328a36",
                "border": "#1b1b1b"
            },
        font={
            "color": "#ffffff",
            "size": 20,
            "face": "arial",
            "bold": True
        },
            shape="circle",
            size=30
        )

        relation = "PRIMARY SUBSET" if item["rank"] <= 3 else "SECONDARY SUBSET"

        if relation == "PRIMARY SUBSET":
            edge_color = "#10b981"   # green
        else:
            edge_color = "#f59e0b"   # orange

        net.add_edge(
            selected_control,
            item["mapping"],
            label=f"{relation}\n{score_percent:.0f}%",
            title=f"{relation} | {item['confidence']}",
            value=max(score_percent / 25, 1),
            width=2 if relation == "PRIMARY SUBSET" else 2,
            color={
                "color": "#dcd2d2",
                "highlight": edge_color,
                "hover": edge_color
            },
            font={
                "color": edge_color,
                "size": 16,
                "face": "arial",
                "strokeWidth": 1,
                "strokeColor": "#ffffff",
                "align": "middle"
            }
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp:
        net.save_graph(tmp.name)
        with open(tmp.name, "r", encoding="utf-8") as f:
            return f.read()


# -------------------------
# SIDEBAR
# -------------------------
st.sidebar.markdown('<div class="sidebar-title">Select Standard:</div>', unsafe_allow_html=True)

standard = st.sidebar.selectbox(
    "",
    ["ECC (Essential Cybersecurity Controls)"],
    label_visibility="collapsed"
)

tab_choice = st.sidebar.radio(
    "",
    ["📊 Mappings", "📈 Analytics"],
    horizontal=True
)


DATA_PATH = "final_ontology_refined_mappings_with_explanations.csv" 

if os.path.exists(DATA_PATH):
    df = pd.read_csv(DATA_PATH)
else:
   
    uploaded_file = st.file_uploader("Custom CSV for ECC (File not found locally):", type=["csv"])
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
    else:
        st.markdown('<div class="main-title">Control Mapping Viewer</div>', unsafe_allow_html=True)
        st.info(f"Please ensure '{DATA_PATH}' is in the repository or upload it here.")
        st.stop()


# -------------------------
# LOAD DATA PROCESSING
# -------------------------
control_col = "ECC id control"
source_col = "Source Text"

if control_col not in df.columns or source_col not in df.columns:
    st.error("Your CSV must contain: ECC id control and Source Text")
    st.stop()

controls_df = df[[control_col, source_col]].dropna().copy()
controls_df[control_col] = controls_df[control_col].astype(str)

st.sidebar.markdown(
    f'<div class="sidebar-title">Controls ({len(controls_df)})</div>',
    unsafe_allow_html=True
)

search = st.sidebar.text_input(
    "",
    placeholder="Search by control number (e.g., 2.4)"
)

if search:
    controls_df = controls_df[
        controls_df[control_col].str.contains(search, case=False, na=False)
    ]

control_options = controls_df[control_col].tolist()

if "selected_control" not in st.session_state:
    st.session_state.selected_control = controls_df[control_col].astype(str).iloc[0]

# --- Sidebar CSS Styles ---
st.sidebar.markdown("""
<style>
[data-testid="stSidebar"] div.stButton > button {
    width: 100%;
    height: auto;
    min-height: 120px;
    text-align: left;
    justify-content: flex-start;
    align-items: flex-start;
    white-space: normal;
    padding: 14px;
    border-radius: 6px;
    border: 1px solid #e5e5e5;
    background-color: #ffffff;
    color: #444;
    margin-bottom: 8px;
}
[data-testid="stSidebar"] div.stButton > button:hover {
    background-color: #eaf6ff;
    border: 1px solid #1476d4;
    color: #1476d4;
}
.selected-control-card button {
    background-color: #dff0ff !important;
    border: 2px solid #1476d4 !important;
}
</style>
""", unsafe_allow_html=True)


def count_mappings(row):
    count = 0
    for i in range(1, 11):
        col = "NIST mapping" if i == 1 else f"NIST mapping {i}"
        if col in df.columns and pd.notna(row.get(col)):
            count += 1
    return count

st.sidebar.markdown("### Controls")
control_box = st.sidebar.container(height=520, border=True)

with control_box:
    for i, r in controls_df.iterrows():
        cid = str(r[control_col])
        preview = short_text(r[source_col], 160)
        full_row = df[df[control_col].astype(str) == cid].iloc[0]
        count = count_mappings(full_row)
        label = f"{cid}\n\n{preview}\n\n{count} recommended mappings"

        if cid == st.session_state.selected_control:
            st.markdown('<div class="selected-control-card">', unsafe_allow_html=True)
        if st.button(label, key=f"control_btn_{i}"):
            st.session_state.selected_control = cid
            st.rerun()
        if cid == st.session_state.selected_control:
            st.markdown("</div>", unsafe_allow_html=True)


selected_control = st.session_state.selected_control
row = df[df[control_col].astype(str) == selected_control].iloc[0]
source_text = str(row[source_col])
top_k = st.slider("Top-K:", 1, 10, 10)
mappings = extract_mappings(row, df, top_k)


# -------------------------
# MAIN INTERFACE (TABS)
# -------------------------
if tab_choice == "📊 Mappings":
    st.markdown('<div class="main-title">Control Mapping Viewer</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="subtitle">Viewing: <b>{selected_control}</b></div>', unsafe_allow_html=True)

    
    left, right = st.columns([3.0, 1.8]) 

    with left:
        st.markdown('<div class="graph-box">', unsafe_allow_html=True)
        graph_html = create_graph(selected_control, source_text, mappings)
        components.html(graph_html, height=650)
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown("### Mapping Details")
        
        card_container = st.container(height=650)
        with card_container:
            for item in mappings:
               
                st.markdown(f"""
                <div class="mapping-card">
                    <span class="rank-pill">#{item['rank']}</span>
                    <span class="mapping-title">{item['mapping']}</span>
                    <div class="mapping-text">{item['text']}</div>
                </div>
                """, unsafe_allow_html=True)
# -------------------------
elif tab_choice == "📈 Analytics":

    def get_all_mappings(df):
        all_items = []
        for _, row in df.iterrows():
            control_id = str(row[control_col])
            for i in range(1, 11):
                cols = get_mapping_columns(i)
                if cols["mapping"] not in df.columns:
                    continue
                mapping_value = row.get(cols["mapping"])
                if pd.isna(mapping_value) or str(mapping_value).strip() == "":
                    continue
                all_items.append({
                    "control": control_id,
                    "mapping": str(mapping_value),
                    "dense": float(row.get(cols["dense"], 0) or 0),
                    "sparse": float(row.get(cols["sparse"], 0) or 0),
                    "hybrid": float(row.get(cols["hybrid"], 0) or 0),
                    "ontology": float(row.get(cols["ontology"], 0) or 0),
                    "final": float(row.get(cols["final"], 0) or 0),
                    "confidence": str(row.get(cols["confidence"], "")),
                    "rank": i
                })
        return pd.DataFrame(all_items)

    analytics_all = get_all_mappings(df)
    total_controls = len(df)
    total_mappings = len(analytics_all)
    avg_mappings = total_mappings / total_controls if total_controls else 0

    controls_with_mappings = analytics_all["control"].nunique()
    controls_without_mappings = total_controls - controls_with_mappings

    avg_embedding = analytics_all["dense"].mean() * 100 if not analytics_all.empty else 0
    avg_ontology = analytics_all["ontology"].mean() * 100 if not analytics_all.empty else 0
    avg_jaccard = analytics_all["sparse"].mean() * 100 if not analytics_all.empty else 0

    with_counts = controls_with_mappings / total_controls * 100 if total_controls else 0
    without_counts = controls_without_mappings / total_controls * 100 if total_controls else 0

    st.markdown("""
    <style>
    .analytics-card {
        background: white; border-radius: 16px; padding: 28px; margin-bottom: 26px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08); border: 1px solid #eeeeee;
    }
    .section-title { font-size: 28px; font-weight: 800; margin-bottom: 18px; color: #0f172a; border-bottom: 3px solid #e5e7eb; padding-bottom: 16px; }
    .metric-box { border: 2px solid #e5e7eb; border-radius: 10px; padding: 28px; text-align: center; background: #f8fafc; }
    .metric-number { font-size: 52px; font-weight: 900; color: #1f2937; }
    .metric-label { font-size: 20px; color: #596579; font-weight: 600; }
    .gap-warning { border: 3px solid #f59e0b; background: #fff9e8; border-radius: 10px; padding: 30px; text-align: center; }
    .gap-success { border: 3px solid #10 b981; background: #e9fff3; border-radius: 10px; padding: 30px; text-align: center; }
    .orange-number { font-size: 54px; font-weight: 900; color: #f59e0b; }
    .green-number { font-size: 54px; font-weight: 900; color: #10b981; }
    .progress-bg { width: 100%; height: 12px; background: #e5e7eb; border-radius: 20px; overflow: hidden; margin-top: 12px; }
    .progress-blue { height: 100%; background: linear-gradient(90deg, #3b82f6, #6366f1); border-radius: 20px; }
    .progress-purple { height: 100%; background: #8b5cf6; border-radius: 20px; }
    .progress-green { height: 100%; background: #10b981; border-radius: 20px; }
    .progress-orange { height: 100%; background: #f59e0b; border-radius: 20px; }
    .progress-red { height: 100%; background: #ef4444; border-radius: 20px; }
    .relation-box { border: 2px solid #e5e7eb; border-radius: 10px; padding: 28px; background: #f8fafc; }
    .relation-title { text-align: center; font-size: 22px; font-weight: 800; color: #596579; margin-bottom: 24px; }
    .relation-row { margin-bottom: 24px; font-size: 18px; font-weight: 700; }
    .relation-value { float: right; color: #596579; font-weight: 600; }
    .reciprocal-box { border: 3px solid #10b981; background: #e9fff3; border-radius: 14px; padding: 36px; display: flex; align-items: center; justify-content: space-around; }
    .big-green { font-size: 86px; font-weight: 900; color: #10b981; text-align: center; }
    .table-head { background: #f1f3f6; font-weight: 800; padding: 18px; border-bottom: 2px solid #e5e7eb; }
    .table-row { padding: 18px; border-bottom: 1px solid #e5e7eb; font-size: 18px; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

    # OVERVIEW
    st.markdown('<div class="analytics-card"><div class="section-title">Overview</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="metric-box"><div class="metric-number">{total_controls}</div><div class="metric-label">Total ECC Controls</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-box"><div class="metric-number">{total_mappings}</div><div class="metric-label">Total Recommended Mappings</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-box"><div class="metric-number">{avg_mappings:.1f}</div><div class="metric-label">Avg Mappings per Control</div></div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # GAP ANALYSIS
    st.markdown('<div class="analytics-card"><div class="section-title">Gap Analysis</div>', unsafe_allow_html=True)
    g1, g2 = st.columns(2)
    with g1:
        st.markdown(f'<div class="gap-warning"><div class="orange-number">{controls_without_mappings}</div><div class="metric-label">Controls with 0 Mappings</div><br><div style="color:#94a3b8;font-weight:700;">{without_counts:.1f}% of total</div></div>', unsafe_allow_html=True)
    with g2:
        st.markdown(f'<div class="gap-success"><div class="green-number">{controls_with_mappings}</div><div class="metric-label">Controls with Mappings</div><br><div style="color:#94a3b8;font-weight:700;">{with_counts:.1f}% coverage</div></div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # SIMILARITY SCORES
    st.markdown('<div class="analytics-card"><div class="section-title">Average Similarity Scores</div>', unsafe_allow_html=True)
    s1, s2, s3 = st.columns(3)
    with s1:
        st.markdown(f'<div class="metric-box"><div class="metric-number">{avg_embedding:.1f}%</div><div class="metric-label">Avg Embedding Score</div><div class="progress-bg"><div class="progress-blue" style="width:{avg_embedding}%;"></div></div></div>', unsafe_allow_html=True)
    with s2:
        st.markdown(f'<div class="metric-box"><div class="metric-number">{avg_ontology:.1f}%</div><div class="metric-label">Avg Ontology Score</div><div class="progress-bg"><div class="progress-purple" style="width:{avg_ontology}%;"></div></div></div>', unsafe_allow_html=True)
    with s3:
        st.markdown(f'<div class="metric-box"><div class="metric-number">{avg_jaccard:.1f}%</div><div class="metric-label">Avg Jaccard Similarity</div><div class="progress-bg"><div class="progress-green" style="width:{avg_jaccard}%;"></div></div></div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()
