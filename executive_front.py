"""CONSEDE Executive Front design system.

Shared visual language based on the approved 4MSFTS command-center reference.
Presentation-only CSS: no scoring, data, persistence, or workflow logic.
"""
import streamlit as st


def apply_executive_theme():
    st.markdown(
        """
        <style>
        :root {
          --cns-navy: #142f43;
          --cns-navy-2: #1b3b52;
          --cns-teal: #12b5a5;
          --cns-green: #78b85e;
          --cns-gold: #d5ad59;
          --cns-red: #d64550;
          --cns-ink: #172f42;
          --cns-muted: #71879a;
          --cns-canvas: #f1f5f7;
          --cns-line: #dce5e9;
        }
        html, body, [data-testid="stAppViewContainer"] {
          background: var(--cns-canvas);
          color: var(--cns-ink);
          font-family: Inter, "Segoe UI", Arial, sans-serif;
        }
        [data-testid="stHeader"] { background: var(--cns-teal); height: 5px; }
        [data-testid="stToolbar"] { top: .35rem; }
        .block-container { max-width: 1540px; padding-top: 2.1rem; padding-bottom: 2.8rem; }
        [data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {
          background: var(--cns-navy);
          border-right: 1px solid #29485c;
        }
        [data-testid="stSidebar"] * { color: #e6eef3; }
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 { color: #fff !important; letter-spacing: .01em; }
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] .stCaption { color: #a9bdca !important; }
        h1, h2, h3, h4 { color: var(--cns-ink) !important; letter-spacing: -.025em; }
        h1 { font-size: clamp(1.8rem, 2.4vw, 2.35rem) !important; font-weight: 750 !important; }
        h2 { font-size: 1.48rem !important; font-weight: 720 !important; }
        h3 { font-size: 1.13rem !important; font-weight: 700 !important; }
        p, li, label, [data-testid="stCaptionContainer"] { color: #526b7d; }
        [data-testid="stMetric"] {
          background: #fff; border: 1px solid var(--cns-line);
          border-left: 5px solid var(--cns-teal); border-radius: 12px;
          padding: 15px 17px; box-shadow: 0 2px 5px rgba(18,42,58,.10);
          min-height: 112px;
        }
        [data-testid="stMetricLabel"] p {
          color: #71879a !important; font-size: .76rem !important;
          font-weight: 750 !important; letter-spacing: .035em; text-transform: uppercase;
        }
        [data-testid="stMetricValue"] {
          color: var(--cns-ink) !important;
          font-size: clamp(1.35rem, 2vw, 1.9rem) !important; font-weight: 780 !important;
        }
        [data-testid="stForm"], [data-testid="stExpander"],
        [data-testid="stDataFrame"], [data-testid="stTable"] {
          background: #fff; border: 1px solid var(--cns-line); border-radius: 11px;
        }
        [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea,
        [data-testid="stNumberInput"] input,
        [data-testid="stSelectbox"] [data-baseweb="select"] > div,
        [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
          background: #fff; border-color: #cbd8df; border-radius: 8px;
        }
        [data-testid="stTabs"] [data-baseweb="tab-list"] {
          gap: .35rem; border-bottom: 1px solid var(--cns-line);
        }
        [data-testid="stTabs"] button[role="tab"] {
          color: #5c7485; font-weight: 650; padding: .7rem 1rem;
        }
        [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
          color: var(--cns-teal); border-bottom: 3px solid var(--cns-teal);
        }
        .stButton > button, .stDownloadButton > button,
        [data-testid="stFormSubmitButton"] > button {
          border-radius: 8px; border: 1px solid #cbd8df;
          font-weight: 700; min-height: 2.55rem;
          transition: transform .12s ease, box-shadow .12s ease;
        }
        .stButton > button[kind="primary"],
        [data-testid="stFormSubmitButton"] > button[kind="primary"] {
          background: var(--cns-teal); color: #fff; border-color: var(--cns-teal);
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
          transform: translateY(-1px); box-shadow: 0 3px 9px rgba(18,42,58,.14);
        }
        [data-testid="stAlert"] { border-radius: 9px; border-width: 1px; }
        hr { border-color: var(--cns-line); }
        .cns-command-head { display:flex; justify-content:space-between; align-items:flex-start; gap:1rem; margin: .6rem 0 2rem; }
        .cns-eyebrow { color:#71879a; font-size:.72rem; font-weight:800; letter-spacing:.12em; margin-bottom:.55rem; }
        .cns-command-head h1 { font-size:2.35rem !important; margin:0; }
        .cns-command-head p { margin:.45rem 0 0; color:#71879a; font-size:.96rem; }
        .cns-page-index { color:#71879a; font-size:.75rem; font-weight:750; padding-top:.25rem; }
        .cns-kpi-card { background:#fff; min-height:136px; border:1px solid #dce5e9; border-left:6px solid #12b5a5; border-radius:13px; padding:17px 17px 14px; box-shadow:0 2px 5px rgba(18,42,58,.12); margin-bottom:1.55rem; }
        .cns-green { border-left-color:#78b85e; } .cns-gold { border-left-color:#d5ad59; } .cns-red { border-left-color:#d64550; } .cns-teal { border-left-color:#12b5a5; }
        .cns-kpi-label { color:#71879a; font-size:.68rem; font-weight:800; letter-spacing:.045em; }
        .cns-kpi-title { color:#172f42; font-size:1.8rem; line-height:1.15; font-weight:800; margin:.72rem 0 .55rem; }
        .cns-kpi-value { color:#172f42; font-size:.84rem; font-weight:750; }
        .cns-kpi-note { color:#8295a4; font-size:.69rem; margin-top:.35rem; }
        .cns-command-grid { display:grid; grid-template-columns:1.35fr 1fr; gap:1.2rem; margin:.2rem 0 1.2rem; }
        .cns-command-panel { background:transparent; padding:.2rem .4rem; }
        .cns-panel-title { color:#172f42; font-size:1.18rem; font-weight:780; margin-bottom:1.2rem; }
        .cns-progress-row { display:grid; grid-template-columns: minmax(125px, .8fr) minmax(130px, 1.7fr) 52px 68px; gap:.7rem; align-items:center; margin:1.15rem 0; }
        .cns-progress-label { color:#71879a; font-size:.76rem; }
        .cns-progress-track { height:15px; border-radius:4px; background:#dfe7ea; overflow:hidden; box-shadow:inset 0 1px 2px rgba(0,0,0,.08); }
        .cns-progress-fill { height:100%; border-radius:3px; }
        .cns-fill-teal { background:#12b5a5; } .cns-fill-green { background:#78b85e; } .cns-fill-gold { background:#d5ad59; } .cns-fill-navy { background:#18384e; } .cns-fill-muted { background:#9fb1bc; }
        .cns-progress-value { color:#172f42; font-size:.77rem; font-weight:750; text-align:right; }
        .cns-progress-tag { color:#172f42; font-size:.7rem; font-weight:750; }
        .cns-attention-panel { padding-left:1.1rem; }
        .cns-attention-item { display:flex; gap:.8rem; align-items:flex-start; margin:1.35rem 0; }
        .cns-attention-item span { flex:0 0 11px; width:11px; height:11px; background:#12b5a5; border-radius:2px; margin-top:.28rem; box-shadow:0 1px 3px rgba(0,0,0,.2); }
        .cns-attention-item p { margin:0; color:#526b7d; font-size:.84rem; }
        .cns-command-footer { color:#172f42; font-size:1.02rem; font-weight:780; margin:2.1rem .4rem 2.3rem; }
        @media(max-width:1000px) { .cns-command-grid { grid-template-columns:1fr; } .cns-kpi-title {font-size:1.4rem;} .cns-progress-row {grid-template-columns:1fr 1.5fr 42px 58px; gap:.4rem;} }
        @media (max-width: 900px) {
          .block-container { padding-left: 1.1rem; padding-right: 1.1rem; }
          [data-testid="stMetric"] { min-height: 96px; padding: 11px 12px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )



def render_command_center(metrics=None):
    """Render the approved executive command-center overview using live run metrics only."""
    data = metrics or {}
    raw = int(data.get("raw", 0) or 0)
    eligible = int(data.get("eligible", 0) or 0)
    aaa = int(data.get("aaa", 0) or 0)
    aa = int(data.get("aa", 0) or 0)
    leads = aaa + aa
    has_run = bool(metrics)

    st.markdown(
        """
        <div class="cns-command-head">
          <div>
            <div class="cns-eyebrow">4MSFTS · COMMERCIAL INTELLIGENCE</div>
            <h1>Centro de mando</h1>
            <p>Una lectura ejecutiva del universo, los leads prioritarios y la actividad comercial.</p>
          </div>
          <div class="cns-page-index">01 / 12</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cards = [
        ("UNIVERSO OBJETIVO", "BASE", f"{raw:,}" if has_run else "—", "empresas de origen", "teal"),
        ("EMPRESAS FILTRADAS", "PERFIL", f"{eligible:,}" if has_run else "—", "coincidencia comercial", "green"),
        ("LEADS PRIORITARIOS", "AAA / AA", f"{leads:,}" if has_run else "—", "por atender primero", "gold"),
        ("SEÑALES DETECTADAS", "RADAR", "EXPEDIENTE", "evidencia por empresa", "red"),
        ("CAMPAÑAS", "MAILING", "ACTIVACIÓN", "envío y seguimiento", "teal"),
    ]
    cols = st.columns(5, gap="medium")
    for col, card in zip(cols, cards):
        label, title, value, note, accent = card
        with col:
            st.markdown(
                f"""
                <div class="cns-kpi-card cns-{accent}">
                  <div class="cns-kpi-label">{label}</div>
                  <div class="cns-kpi-title">{title}</div>
                  <div class="cns-kpi-value">{value}</div>
                  <div class="cns-kpi-note">{note}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown(
        """
        <div class="cns-command-grid">
          <section class="cns-command-panel">
            <div class="cns-panel-title">Lectura del universo comercial</div>
        """,
        unsafe_allow_html=True,
    )
    if has_run:
        stages = [
            ("Universo identificado", raw, raw, "teal", "Base"),
            ("Perfil validado", eligible, raw, "green", "Filtro"),
            ("Prioridad alta", leads, raw, "gold", "AAA / AA"),
            ("Por validar", int(data.get("validar", 0) or 0), raw, "navy", "VALIDAR"),
        ]
        for label, value, maximum, color, tag in stages:
            ratio = min(100.0, (value / maximum * 100)) if maximum else 0
            st.markdown(
                f"""
                <div class="cns-progress-row">
                  <div class="cns-progress-label">{label}</div>
                  <div class="cns-progress-track"><div class="cns-progress-fill cns-fill-{color}" style="width:{ratio:.2f}%"></div></div>
                  <div class="cns-progress-value">{value:,}</div>
                  <div class="cns-progress-tag">{tag}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        for label, tag in [
            ("Universo identificado", "BASE"),
            ("Perfil validado", "FILTRO"),
            ("Prioridad alta", "AAA / AA"),
            ("Por validar", "VALIDAR"),
        ]:
            st.markdown(
                f"""
                <div class="cns-progress-row">
                  <div class="cns-progress-label">{label}</div>
                  <div class="cns-progress-track"><div class="cns-progress-fill cns-fill-muted" style="width:0%"></div></div>
                  <div class="cns-progress-value">—</div>
                  <div class="cns-progress-tag">{tag}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.markdown(
        """
          </section>
          <section class="cns-command-panel cns-attention-panel">
            <div class="cns-panel-title">Atención ejecutiva</div>
            <div class="cns-attention-item"><span></span><p>Empresas con mejor ajuste al perfil objetivo</p></div>
            <div class="cns-attention-item"><span></span><p>Señales que justifican contacto comercial, con evidencia individual</p></div>
            <div class="cns-attention-item"><span></span><p>Campañas listas para revisión, aprobación y medición</p></div>
          </section>
        </div>
        <div class="cns-command-footer">
          CONSEDE conecta identificación, priorización y contacto en un mismo proceso trazable.
        </div>
        """,
        unsafe_allow_html=True,
    )
