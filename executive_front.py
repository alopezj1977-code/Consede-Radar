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
        @media (max-width: 900px) {
          .block-container { padding-left: 1.1rem; padding-right: 1.1rem; }
          [data-testid="stMetric"] { min-height: 96px; padding: 11px 12px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
