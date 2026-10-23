# app.py
# CONCEDE V3 — Motor de Generación de Demanda
# Arquitectura: UI ejecutiva V2 + motor matemático V3.
# IMPORTANTE: este archivo NO replica ni modifica la lógica V2.
# Toda la puntuación V3 se ejecuta mediante core.py + concede_v3.json.

from pathlib import Path
import datetime
import io
import json

import pandas as pd
import plotly.express as px
import streamlit as st

from core import load_config, run, ConfigError, identify_columns
from radar_ui import render_radar_ui


# ============================================================
# CONFIGURACIÓN
# ============================================================

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "concede_v3.json"

CFG = load_config(CONFIG_PATH)

st.set_page_config(
    page_title="CONCEDE | Motor de Generación de Demanda",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

ENTIDADES = CFG["geography"]["entities"]
ENTITY_OPTIONS = ["TODAS LAS ENTIDADES"] + ENTIDADES
DEFAULT_MIN_EMP = int(CFG["eligibility"]["employee_minimum"])
DEFAULT_MAX_EMP = CFG["eligibility"].get("employee_maximum")
TICKET_DEFAULT = float(CFG["pipeline"]["ticket_promedio_mxn"])


# ============================================================
# ESTILO EJECUTIVO
# ============================================================

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.35rem;
        padding-bottom: 2rem;
        max-width: 1500px;
    }

    /* Tipografía global: evita que títulos Markdown de fuentes externas
       se conviertan en bloques gigantes dentro de la interfaz. */
    [data-testid="stAppViewContainer"] .stMarkdown h1 {
        font-size: 1.45rem !important;
        line-height: 1.25 !important;
    }
    [data-testid="stAppViewContainer"] .stMarkdown h2 {
        font-size: 1.25rem !important;
        line-height: 1.3 !important;
    }
    [data-testid="stAppViewContainer"] .stMarkdown h3 {
        font-size: 1.08rem !important;
        line-height: 1.35 !important;
    }
    [data-testid="stAppViewContainer"] .stMarkdown h4,
    [data-testid="stAppViewContainer"] .stMarkdown h5,
    [data-testid="stAppViewContainer"] .stMarkdown h6 {
        font-size: 0.98rem !important;
        line-height: 1.4 !important;
    }
    [data-testid="stAppViewContainer"] .stMarkdown p,
    [data-testid="stAppViewContainer"] .stMarkdown li {
        font-size: 0.94rem !important;
        line-height: 1.5 !important;
    }

    [data-testid="stMetric"] {
        background: #f4f7fb;
        border: 1px solid #dce4ef;
        padding: 12px 14px;
        border-radius: 12px;
    }

    .hero {
        background: linear-gradient(135deg, #0b1f3a 0%, #163a63 100%);
        color: white;
        padding: 22px 26px;
        border-radius: 16px;
        margin-bottom: 18px;
    }

    .hero h1 {
        margin: 0;
        font-size: 2rem;
        line-height: 1.15;
    }

    .hero p {
        margin: 7px 0 0 0;
        color: #d9e5f3;
    }

    .section-title {
        font-size: 1.15rem;
        font-weight: 700;
        margin-top: 0.4rem;
        margin-bottom: 0.4rem;
    }

    .small-note {
        color: #64748b;
        font-size: 0.86rem;
    }

    .kpi-note {
        color: #64748b;
        font-size: 0.78rem;
    }

    .status-ok {
        background: #ecfdf5;
        border: 1px solid #a7f3d0;
        padding: 9px 12px;
        border-radius: 9px;
        color: #065f46;
    }

    .status-info {
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        padding: 9px 12px;
        border-radius: 9px;
        color: #1e40af;
    }

    .status-warn {
        background: #fffbeb;
        border: 1px solid #fde68a;
        padding: 9px 12px;
        border-radius: 9px;
        color: #92400e;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# FUNCIONES AUXILIARES DE UI
# ============================================================

def money(value):
    return f"${float(value):,.0f}"


def pct(value):
    return f"{float(value):.2f}%"


def read_source(uploaded_file):
    """Lee CSV/XLSX sin modificar la fuente."""
    if uploaded_file is None:
        return None

    try:
        name = uploaded_file.name.lower()
        if name.endswith(".csv"):
            try:
                return pd.read_csv(uploaded_file, encoding="utf-8", low_memory=False)
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, encoding="latin1", low_memory=False)
        return pd.read_excel(uploaded_file)
    except Exception as exc:
        st.error(f"No fue posible leer la fuente: {exc}")
        return None


def make_need_evidence(enabled, storage, fleet, technology, urgency):
    if not enabled:
        return None
    return {
        "almacenamiento": int(storage),
        "flota": int(fleet),
        "tecnologia": int(technology),
        "urgencia": int(urgency),
    }


def add_identity_columns(df):
    mapping = identify_columns(df)
    preferred = [
        mapping.get("id"),
        mapping.get("nom_estab"),
        mapping.get("raz_social"),
        mapping.get("nombre_act"),
        mapping.get("entidad"),
        mapping.get("municipio"),
    ]
    return [c for c in preferred if c and c in df.columns]


def commercial_funnel(aaa, ticket):
    """
    Funnel de referencia V2.
    Se mantiene como vista ejecutiva y NO modifica el cálculo V3.
    """
    rates = {
        "AAA": 1.00,
        "Decisor ubicado": 1591 / 1989,
        "Conexión aceptada": 557 / 1989,
        "Respuesta positiva": 139 / 1989,
        "Cita": 56 / 1989,
        "Reunión": 42 / 1989,
        "Cierre": 8 / 1989,
    }

    rows = []
    for label, rate in rates.items():
        if label == "AAA":
            value = aaa
        else:
            value = round(aaa * rate)
        rows.append({"Etapa": label, "Cuentas": int(value)})

    return pd.DataFrame(rows)


def priority_counts(df):
    if df is None or df.empty:
        return {"AAA": 0, "AA": 0, "VALIDAR": 0}
    s = df.loc[df["Candidato_Comercial"], "Prioridad"]
    return {
        "AAA": int((s == "AAA").sum()),
        "AA": int((s == "AA").sum()),
        "VALIDAR": int((s == "VALIDAR").sum()),
    }


# ============================================================
# ENCABEZADO
# ============================================================

st.markdown(
    f"""
    <div class="hero">
        <h1>CONCEDE | Motor de Generación de Demanda</h1>
        <p>Motor V3 · UI ejecutiva · {len(ENTIDADES)} entidades · Score / Prioridad / Valor Potencial separados</p>
    </div>
    """,
    unsafe_allow_html=True,
)

top1, top2, top3 = st.columns([2.2, 1.2, 1.2])
with top1:
    st.markdown(
        '<div class="status-ok"><b>Entorno de Pruebas</b> · Branch motor-v3 · Motor 3.0.0-FINAL</div>',
        unsafe_allow_html=True,
    )
with top2:
    st.caption("Modo")
    st.write("**Ejecución V3**")
with top3:
    st.caption("Reglas")
    st.write("**Sin fallbacks silenciosos**")


# ============================================================
# SIDEBAR — CONFIGURACIÓN DE CORRIDA
# ============================================================

with st.sidebar:
    st.header("🎯 Cliente objetivo")
    cliente_objetivo = st.text_input(
        "Cliente / proyecto",
        value="CONSEDE",
        help="Identificador comercial de la corrida. No altera el score.",
    )

    st.divider()
    st.header("🗺️ Cobertura geográfica P0.2")
    selected_entities = st.multiselect(
        "Entidades objetivo",
        ENTITY_OPTIONS,
        default=["TODAS LAS ENTIDADES"],
        help="P0.2 controla cobertura geográfica. No crea un filtro adicional oculto.",
    )

    if not selected_entities:
        st.warning("Selecciona al menos una entidad.")
        selected_entities = ["TODAS LAS ENTIDADES"]

    if "TODAS LAS ENTIDADES" in selected_entities:
        effective_entities = ENTIDADES
        geo_label = "Todas las entidades"
    else:
        effective_entities = selected_entities
        geo_label = f"{len(selected_entities)} entidad(es)"

    st.caption(f"Cobertura activa: **{geo_label}**")

    st.divider()
    st.header("👥 Elegibilidad")
    employee_minimum = st.number_input(
        "Mínimo de empleados",
        min_value=0,
        value=DEFAULT_MIN_EMP,
        step=1,
    )

    max_default = 0 if DEFAULT_MAX_EMP is None else int(DEFAULT_MAX_EMP)
    employee_maximum_ui = st.number_input(
        "Máximo de empleados (0 = sin límite)",
        min_value=0,
        value=max_default,
        step=1,
    )

    employee_maximum = None if employee_maximum_ui == 0 else int(employee_maximum_ui)

    st.caption(
        "La elegibilidad es configurable por corrida. "
        "El 11+ de V2 se conserva únicamente como referencia de compatibilidad."
    )

    st.divider()
    st.header("💰 Parámetros comerciales")
    ticket = st.number_input(
        "Ticket promedio (MXN)",
        min_value=0.0,
        value=TICKET_DEFAULT,
        step=1000.0,
        format="%.0f",
    )
    st.caption("Pipeline = AAA × ticket. El ticket no modifica el Score V3.")

    st.divider()
    st.header("🧠 Necesidad")
    need_enabled = st.checkbox(
        "Capturar evidencia comercial",
        value=False,
        help="Sin evidencia, Score_Necesidad = 0. No se infiere desde DENUE.",
    )

    need_values = CFG["need"]["scale"]
    if need_enabled:
        storage = st.select_slider(
            "Almacenamiento",
            options=need_values,
            value=0,
        )
        fleet = st.select_slider(
            "Flota",
            options=need_values,
            value=0,
        )
        technology = st.select_slider(
            "Tecnología",
            options=need_values,
            value=0,
        )
        urgency = st.select_slider(
            "Urgencia / estacionalidad",
            options=need_values,
            value=0,
        )
    else:
        storage = fleet = technology = urgency = 0
        st.info("Sin evidencia comercial → Score_Necesidad = 0")

    st.divider()
    st.header("📂 Fuente DENUE / Base")
    uploaded = st.file_uploader(
        "Carga CSV o Excel",
        type=["csv", "xlsx"],
        help="CONCEDE V3 procesa únicamente la fuente cargada.",
    )

    run_label = st.text_input(
        "Run_ID (opcional)",
        value="",
        placeholder="CONCEDE-YYYYMMDD-001",
    )

    execute = st.button(
        "▶ Ejecutar CONCEDE V3",
        type="primary",
        use_container_width=True,
    )


# ============================================================
# ESTADO INICIAL
# ============================================================

if "concede_result" not in st.session_state:
    st.session_state.concede_result = None

if "concede_metrics" not in st.session_state:
    st.session_state.concede_metrics = None

if "concede_source_name" not in st.session_state:
    st.session_state.concede_source_name = None

if execute:
    if uploaded is None:
        st.error("Carga una fuente CSV/XLSX antes de ejecutar.")
        st.stop()

    df = read_source(uploaded)

    if df is None:
        st.stop()

    run_id = (
        run_label.strip()
        or datetime.datetime.now().strftime("CONCEDE-%Y%m%d-%H%M%S")
    )

    need_evidence = make_need_evidence(
        need_enabled,
        storage,
        fleet,
        technology,
        urgency,
    )

    try:
        result, metrics = run(
            df=df,
            cfg=CFG,
            selected_entities=effective_entities,
            run_id=run_id,
            need_evidence=need_evidence,
            employee_minimum=int(employee_minimum),
            employee_maximum=employee_maximum,
        )

        # El motor V3 calcula el ticket desde configuración.
        # El parámetro comercial de UI se conserva como vista.
        # Para evitar modificar silenciosamente el contrato, el pipeline
        # oficial mostrado usa el ticket cerrado del config V3.
        official_ticket = float(metrics["ticket_promedio_mxn"])

        if float(ticket) != official_ticket:
            st.warning(
                f"El contrato V3 mantiene ticket oficial de {money(official_ticket)}. "
                "El valor capturado en UI no modifica el motor."
            )

        st.session_state.concede_result = result
        st.session_state.concede_metrics = metrics
        st.session_state.concede_source_name = uploaded.name

        st.session_state.concede_client = cliente_objetivo
        st.session_state.concede_geo = geo_label

    except ConfigError as exc:
        st.error(f"Error de contrato V3: {exc}")
        st.stop()
    except Exception as exc:
        st.exception(exc)
        st.stop()


result = st.session_state.concede_result
metrics = st.session_state.concede_metrics


# ============================================================
# SIN CORRIDA
# ============================================================

if result is None or metrics is None:
    st.info(
        "Carga la base en la barra lateral y presiona **Ejecutar CONCEDE V3**. "
        "La interfaz conserva la arquitectura ejecutiva de V2; el cálculo corresponde a V3."
    )

    st.markdown("### Arquitectura de la corrida")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sector", "35%")
    c2.metric("Tamaño", "25%")
    c3.metric("Geografía", "10%")
    c4.metric("Necesidad", "30%")

    st.caption(
        "Clasificación: AAA 80–100 · AA 60–79.99 · VALIDAR <60. "
        "P0.4 Capacidad Propia es informativo y no modifica score."
    )

    # Radar accesible incluso antes de cargar/ejecutar una base V3.
    st.markdown("### Inteligencia de señales y expediente")
    radar_tab_sin_corrida = st.tabs(["🛰️ Radar / Expediente"])[0]
    with radar_tab_sin_corrida:
        render_radar_ui(None, {"run_id": "RUN-SIN-CORRIDA"}, CFG, None, effective_entities)

    st.stop()


# ============================================================
# MÉTRICAS EJECUTIVAS
# ============================================================

raw = int(metrics["raw"])
eligible_count = int(metrics["eligible"])
candidate_count = int(metrics["commercial_candidates"])
aaa = int(metrics["aaa"])
aa = int(metrics["aa"])
validar = int(metrics["validar"])
ticket_official = float(metrics["ticket_promedio_mxn"])
pipeline = float(metrics["valor_potencial"])

penetration = (aaa / eligible_count * 100) if eligible_count else 0.0
avg_score = (
    float(result.loc[result["Candidato_Comercial"], "Score_V3"].mean())
    if result["Candidato_Comercial"].any()
    else 0.0
)

st.markdown("### Funnel de Inteligencia Comercial")

k = st.columns(6)
k[0].metric("Universo", f"{raw:,}")
k[1].metric("Target elegible", f"{eligible_count:,}")
k[2].metric("Candidatos", f"{candidate_count:,}")
k[3].metric("AAA", f"{aaa:,}")
k[4].metric("Penetración AAA", pct(penetration))
k[5].metric("Pipeline potencial", money(pipeline))

st.caption(
    f"Cliente: **{st.session_state.get('concede_client', cliente_objetivo)}** · "
    f"Cobertura: **{st.session_state.get('concede_geo', geo_label)}** · "
    f"Ticket oficial V3: **{money(ticket_official)}** · "
    f"Score promedio candidato: **{avg_score:.2f}**"
)


# ============================================================
# TABS EJECUTIVOS
# ============================================================

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "📋 Matriz de Priorización",
        "📊 Gráficos & Dispersión",
        "🧭 Diagnóstico de Madurez",
        "⚙️ Configuración & Diagnóstico",
        "🛰️ Radar / Expediente",
    ]
)


# ============================================================
# TAB 1 — MATRIZ
# ============================================================

with tab1:
    st.markdown("### Matriz de Priorización")

    p_counts = priority_counts(result)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("AAA", f"{p_counts['AAA']:,}")
    c2.metric("AA", f"{p_counts['AA']:,}")
    c3.metric("VALIDAR", f"{p_counts['VALIDAR']:,}")
    c4.metric("Valor potencial AAA", money(pipeline))

    st.caption(
        "Orden: candidato comercial primero, después Score_V3 descendente. "
        "La tabla muestra trazabilidad de la corrida."
    )

    identity = add_identity_columns(result)

    operational = [
        "Run_ID",
        "Rule_Version",
        "Sector_Comercial",
        "Estrato_Tamano",
        "Score_Sector",
        "Score_Tamano",
        "Score_Geografia",
        "Score_Necesidad",
        "Score_V3",
        "Prioridad",
        "Capacidad_Propia",
        "CRM_Estado",
        "Target_Geografico",
        "Candidato_Comercial",
    ]

    show_cols = []
    for col in identity + operational:
        if col in result.columns and col not in show_cols:
            show_cols.append(col)

    ordered = result.sort_values(
        ["Candidato_Comercial", "Score_V3"],
        ascending=[False, False],
    )

    st.dataframe(
        ordered[show_cols].head(5000),
        use_container_width=True,
        height=560,
    )

    csv_bytes = ordered.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

    d1, d2 = st.columns([1, 1])
    with d1:
        st.download_button(
            "⬇️ Descargar corrida completa CSV",
            data=csv_bytes,
            file_name=f"{metrics['run_id']}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with d2:
        st.download_button(
            "⬇️ Descargar candidatos comerciales CSV",
            data=ordered.loc[
                ordered["Candidato_Comercial"]
            ].to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
            file_name=f"{metrics['run_id']}_candidatos.csv",
            mime="text/csv",
            use_container_width=True,
        )


# ============================================================
# TAB 2 — GRÁFICOS
# ============================================================

with tab2:
    st.markdown("### Gráficos & Dispersión")

    chart_df = result.loc[result["Candidato_Comercial"]].copy()

    if chart_df.empty:
        st.warning("No existen candidatos comerciales con los parámetros actuales.")
    else:
        left, right = st.columns(2)

        with left:
            priority_order = ["AAA", "AA", "VALIDAR"]
            priority_chart = (
                chart_df["Prioridad"]
                .value_counts()
                .reindex(priority_order, fill_value=0)
                .reset_index()
            )
            priority_chart.columns = ["Prioridad", "Cuentas"]

            fig_priority = px.bar(
                priority_chart,
                x="Prioridad",
                y="Cuentas",
                title="Distribución por prioridad",
                text="Cuentas",
            )
            fig_priority.update_layout(showlegend=False)
            st.plotly_chart(fig_priority, use_container_width=True)

        with right:
            sector_chart = (
                chart_df["Sector_Comercial"]
                .value_counts()
                .head(10)
                .reset_index()
            )
            sector_chart.columns = ["Sector", "Cuentas"]

            fig_sector = px.bar(
                sector_chart,
                x="Cuentas",
                y="Sector",
                orientation="h",
                title="Candidatos por sector",
                text="Cuentas",
            )
            fig_sector.update_layout(showlegend=False)
            st.plotly_chart(fig_sector, use_container_width=True)

        st.markdown("#### Dispersión Score V3")

        scatter_cols = [
            "Score_Sector",
            "Score_Tamano",
            "Score_Geografia",
            "Score_Necesidad",
            "Score_V3",
            "Prioridad",
        ]
        scatter_cols = [c for c in scatter_cols if c in chart_df.columns]

        fig_scatter = px.scatter(
            chart_df,
            x="Score_Tamano",
            y="Score_V3",
            color="Prioridad",
            hover_data=scatter_cols,
            title="Score V3 vs. Score de Tamaño",
        )
        fig_scatter.add_hline(y=80, line_dash="dash")
        fig_scatter.add_hline(y=60, line_dash="dot")
        st.plotly_chart(fig_scatter, use_container_width=True)

        st.markdown("#### Funnel de referencia comercial V2")

        funnel = commercial_funnel(aaa, ticket_official)
        fig_funnel = px.funnel(
            funnel,
            y="Etapa",
            x="Cuentas",
            title="Funnel de referencia — no modifica el cálculo V3",
        )
        st.plotly_chart(fig_funnel, use_container_width=True)

        st.caption(
            "El funnel histórico es una vista de referencia. No debe interpretarse "
            "como una predicción estadística del cierre V3."
        )


# ============================================================
# TAB 3 — DIAGNÓSTICO DE MADUREZ
# ============================================================

with tab3:
    st.markdown("### Diagnóstico de Madurez")

    st.info(
        "V3 no infiere necesidad desde DENUE. El diagnóstico de necesidad "
        "solo cambia cuando existe evidencia comercial explícita."
    )

    need_score = float(result["Score_Necesidad"].iloc[0]) if len(result) else 0.0

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Almacenamiento", f"{storage}")
    d2.metric("Flota", f"{fleet}")
    d3.metric("Tecnología", f"{technology}")
    d4.metric("Urgencia", f"{urgency}")

    st.metric("Score Necesidad V3", f"{need_score:.2f}")

    st.markdown("#### Capacidad Propia P0.4")

    cap_counts = result["Capacidad_Propia"].value_counts().reset_index()
    cap_counts.columns = ["Estado", "Cuentas"]

    st.dataframe(cap_counts, use_container_width=True, hide_index=True)

    st.caption(
        "Política V3 cerrada: P0.4 es informativo; no excluye, no modifica score "
        "y no modifica prioridad."
    )


# ============================================================
# TAB 4 — CONFIGURACIÓN Y DIAGNÓSTICO
# ============================================================

with tab4:
    st.markdown("### Configuración & Diagnóstico")

    st.markdown("#### Contrato de puntuación V3")

    weights = CFG["score"]["weights"]
    wc = st.columns(4)
    wc[0].metric("Sector", f"{weights['sector']}%")
    wc[1].metric("Tamaño", f"{weights['size']}%")
    wc[2].metric("Geografía", f"{weights['geography']}%")
    wc[3].metric("Necesidad", f"{weights['need']}%")

    st.markdown("#### Reglas de prioridad")
    priority_table = pd.DataFrame(CFG["priority"]["bands"])
    st.dataframe(priority_table, use_container_width=True, hide_index=True)

    st.markdown("#### Configuración de tamaño")

    size_table = pd.DataFrame(
        [
            {"Estrato": k, "Score": v}
            for k, v in CFG["size"]["scores"].items()
        ]
    )
    st.dataframe(size_table, use_container_width=True, hide_index=True)

    st.markdown("#### Diagnóstico de corrida")

    diag = {
        "Motor": CFG["motor"]["nombre"],
        "Rule_Version": CFG["motor"]["version"],
        "Run_ID": metrics["run_id"],
        "Fuente": st.session_state.get("concede_source_name"),
        "Universo": metrics["raw"],
        "Elegibles": metrics["eligible"],
        "Cobertura geográfica": metrics["target_geography"],
        "Candidatos comerciales": metrics["commercial_candidates"],
        "AAA": metrics["aaa"],
        "AA": metrics["aa"],
        "VALIDAR": metrics["validar"],
        "Ticket oficial MXN": metrics["ticket_promedio_mxn"],
        "Valor potencial MXN": metrics["valor_potencial"],
        "No silent fallbacks": CFG["run"]["no_silent_fallbacks"],
        "P0.4 policy": CFG["capacity_own"]["policy"],
    }

    diag_df = pd.DataFrame(
        [{"Parámetro": k, "Valor": v} for k, v in diag.items()]
    )

    st.dataframe(diag_df, use_container_width=True, hide_index=True)

    st.markdown("#### Compatibilidad histórica V2")

    compat = pd.DataFrame(
        [
            ["Universo bruto", 296441, "Referencia histórica V2"],
            ["Universo elegible", 18410, "Baseline presentado V2"],
            ["AAA", 1711, "Baseline presentado V2"],
            ["Penetración AAA", "9.293862%", "Baseline presentado V2"],
            ["Ticket", "$69,600", "Baseline presentado V2"],
            ["Pipeline", "$119,085,600", "Baseline presentado V2"],
            ["Sensibilidad ≥80", 391, "Control técnico; NO baseline comercial"],
        ],
        columns=["Indicador", "Valor", "Uso"],
    )

    st.dataframe(compat, use_container_width=True, hide_index=True)

    st.warning(
        "La compatibilidad V2 es una referencia de regresión. "
        "No reemplaza ni modifica las reglas matemáticas V3."
    )

    st.markdown("#### Configuración JSON activa")
    st.json(CFG)


# ============================================================
# TAB 5/6 — RADAR + EXPEDIENTE DIGITAL
# ============================================================

with tab5:
    render_radar_ui(result, metrics, CFG, st.session_state.get("concede_source_name"), effective_entities)


# ============================================================
# PIE
# ============================================================

st.divider()

st.caption(
    f"CONCEDE V3 · Run_ID {metrics['run_id']} · Rule_Version {CFG['motor']['version']} · "
    "Fuente → evidencia → decisión → cierre."
)
