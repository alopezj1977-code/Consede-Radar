"""CONCEDE AAA RADAR UI: isolated from V3 scoring and pipeline."""
from __future__ import annotations
from pathlib import Path

import pandas as pd
import streamlit as st

from radar_store import create_company, add_signal, review_signal, get_company_dossier, connect, link_company_denue
from radar_logic import fetch_official_page, hypothesis_from_text
from radar_batch import run_batch, RadarProviderError, RULE_VERSION as BATCH_RULE_VERSION
import os

# Streamlit secrets are not automatically exported as environment variables.
# Load the private Neon URL into this process without printing it.
if not os.getenv("DATABASE_URL"):
    try:
        _database_url = st.secrets.get("DATABASE_URL", "")
        if _database_url:
            os.environ["DATABASE_URL"] = str(_database_url)
    except Exception:
        pass


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "concede_radar.sqlite3"
RULE_VERSION = "RADAR-0.1.0"
SOURCE_CATALOG = {
    "Nuevo León — anuncio oficial de inversión Munters": {
        "url": "https://www.nl.gob.mx/es/boletines/inaugura-munters-su-segunda-planta-en-nuevo-leon-y-refuerza-inversion-industrial-de",
        "type": "INV-EXPANSION", "domain": "www.nl.gob.mx", "state": 'Nuevo León',
        "note": "Fuente oficial estatal; verificar fecha y contenido al consultar."
    },
    "Veracruz — anuncio oficial proyecto energético URSUS": {
        "url": "https://www.veracruz.gob.mx/2026/07/13/confianza-en-veracruz-atrae-proyecto-energetico-de-mas-de-2-mil-millones-de-dolares/",
        "type": "INV-EXPANSION", "domain": "www.veracruz.gob.mx", "state": 'Veracruz',
        "note": "Anuncio de proyecto; distinguir inversión prevista de operación confirmada."
    },
    "Nuevo León — catálogo oficial de nuevas inversiones": {
        "url": "https://www.nl.gob.mx/es/publicaciones/nuevas-inversiones-en-nuevo-leon",
        "type": "INV-EXPANSION", "domain": "www.nl.gob.mx", "state": 'Nuevo León',
        "note": "Catálogo; confirmar vigencia y fecha de cada registro."
    },
    "Veracruz — portal oficial de datos abiertos": {
        "url": "https://datos.veracruzmunicipio.gob.mx/dataset/licencias-de-construccion-a-dic-t4-2024",
        "type": "PERMISO-LICENCIA", "domain": "datos.veracruzmunicipio.gob.mx", "state": 'Veracruz',
        "note": "Dataset histórico de licencias; revisar periodo y columnas antes de inferir actividad actual."
    },
}


def _company_columns(df):
    aliases = {
        "id": ["id", "ID"], "name": ["nom_estab", "nombre establecimiento", "nombre", "empresa"],
        "razon": ["raz_social", "razon social"], "state": ["entidad", "estado"],
        "municipality": ["municipio"], "activity": ["nombre_act", "actividad"],
        "employees": ["per_ocu", "personal ocupado", "empleados"],
    }
    norm = {str(c).strip().lower(): c for c in df.columns}
    return {k: next((norm[a.lower()] for a in opts if a.lower() in norm), None) for k,opts in aliases.items()}

def render_radar_ui(result_df, metrics, config, source_name=None, selected_entities=None):
    st.markdown("## 🛰️ CONCEDE AAA RADAR")
    st.caption("Detección de señales públicas y expediente de evidencia. Radar no modifica el Score ni el pipeline de V3.")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect(DB_PATH) as con:
        company_count = con.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        signal_count = con.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
        pending_count = con.execute("SELECT COUNT(*) FROM signals WHERE human_review_status='PENDIENTE'").fetchone()[0]
    m1,m2,m3 = st.columns(3); m1.metric("Expedientes", company_count); m2.metric("Señales", signal_count); m3.metric("Pendientes de revisión", pending_count)
    tab_radar, tab_batch, tab_dossier, tab_review = st.tabs(["🔎 Radar / nuevas señales", "⚡ Investigación por lote", "📁 Expediente digital", "🧾 Validación humana"])

    with tab_radar:
        st.markdown("### 1. Detectar una señal en una fuente oficial")
        active_entities = {
            str(entity).strip().casefold()
            for entity in (selected_entities or [])
        }
        source_options = {
            label: source for label, source in SOURCE_CATALOG.items()
            if str(source.get("state", "")).strip().casefold() in active_entities
        }
        if source_options:
            src_label = st.selectbox("Fuente candidata", list(source_options.keys()))
            src = source_options[src_label]
        else:
            src_label = "sin_fuente"
            st.warning("No hay fuentes catalogadas para la cobertura P0.2 seleccionada. No se consultará una fuente de otra entidad.")
            src = {"note": "Sin fuentes compatibles con la cobertura activa.", "url": "", "domain": ""}
        st.caption(src["note"])
        st.text_input("URL de la fuente", value=src["url"], disabled=True, key=f"radar_source_url_{src_label}")
        if st.button("Consultar fuente oficial", key="radar_fetch_source", disabled=not bool(source_options)):
            try:
                fetched = fetch_official_page(src["url"], src["domain"])
                st.session_state["radar_fetched"] = {**fetched, "type": src["type"], "source_id": src_label}
                st.success("Página recuperada en vivo. Revisa el título y el extracto antes de guardarlos.")
            except Exception as exc:
                st.session_state.pop("radar_fetched", None)
                st.error(f"La consulta no pudo completarse: {type(exc).__name__}: {exc}. No se registró una señal como si hubiera sido recuperada.")
        fetched = st.session_state.get("radar_fetched")
        if fetched:
            st.write("**Título detectado:**", fetched["title"])
            st.text_area("Extracto recuperado (revisar antes de guardar)", fetched["snippet"], height=130, key="radar_fetched_snippet")
            with st.form("radar_save_fetched"):
                st.markdown("**Asociación empresarial (opcional si la identidad no está confirmada)**")
                display_name = st.text_input("Nombre de establecimiento / empresa", key="radar_company_name")
                state_code = st.selectbox("Entidad", ["No determinada", "Nuevo León", "Veracruz"], key="radar_state")
                municipality = st.text_input("Municipio (si se conoce)")
                source_status = st.selectbox("Estado de fuente", ["INSPECCIONADA", "ACCESIBLE"])
                submitted = st.form_submit_button("Guardar señal y expediente")
            if submitted:
                if not display_name.strip():
                    st.error("Para guardar la señal debes asociarla a una empresa o dejarla como señal regional sin empresa; en esta primera UI ingresa un nombre verificable del comunicado.")
                else:
                    cid = create_company(DB_PATH, display_name, state_code={"Nuevo León":"19","Veracruz":"30"}.get(state_code), municipality=municipality or None)
                    snippet = st.session_state.get("radar_fetched_snippet", fetched["snippet"])
                    hyp, question = hypothesis_from_text(fetched["title"] + " " + snippet, fetched["type"])
                    from datetime import datetime
                    radar_run_id = (metrics or {}).get("run_id")
                    if not radar_run_id or radar_run_id == "RUN-SIN-CORRIDA":
                        radar_run_id = "RADAR-" + datetime.now().strftime("%Y%m%d-%H%M%S")
                    sid = add_signal(DB_PATH, company_id=cid, source_id=fetched["source_id"], source_url=fetched["url"], signal_type=fetched["type"], title=fetched["title"], snippet=snippet, source_status=source_status, identity_status="PENDIENTE_REVISION", need_hypothesis=hyp, next_best_question=question, competition_status="INDETERMINADO", run_id=str(radar_run_id), rule_version=RULE_VERSION, payload={"v3_rule_version": config["motor"]["version"], "v3_source_name": source_name, "heuristic_not_llm": True, "state_label": state_code})
                    st.success(f"Señal guardada: {sid}. Hipótesis heurística marcada como no validada; Score_Impact = 0.")
                    st.session_state.pop("radar_fetched", None)
                    st.rerun()
        st.divider()
        st.markdown("### 2. Crear un expediente desde una empresa del universo actual")
        cols = _company_columns(result_df) if isinstance(result_df, pd.DataFrame) else {}
        if isinstance(result_df, pd.DataFrame) and not result_df.empty and cols.get("name"):
            display = result_df.copy()
            display["_radar_display"] = display[cols["name"]].fillna("").astype(str)
            if cols.get("razon"): display["_radar_display"] = display["_radar_display"].where(display["_radar_display"].str.strip() != "", display[cols["razon"]].fillna("").astype(str))
            options = display["_radar_display"].tolist()
            selected_idx = st.selectbox("Empresa del resultado V3", range(len(options)), format_func=lambda i: options[i], key="radar_v3_company")
            row = display.iloc[int(selected_idx)]
            st.caption("El expediente conserva el identificador DENUE y el contexto de la corrida. Crear expediente no cambia la clasificación.")
            if st.button("Crear / abrir expediente de esta empresa", key="radar_create_from_v3"):
                name = str(row[cols["name"]]).strip() or "Establecimiento sin nombre publicado"
                denue_id = str(row[cols["id"]]) if cols.get("id") and pd.notna(row[cols["id"]]) else None
                state = str(row[cols["state"]]) if cols.get("state") and pd.notna(row[cols["state"]]) else None
                muni = str(row[cols["municipality"]]) if cols.get("municipality") and pd.notna(row[cols["municipality"]]) else None
                with connect(DB_PATH) as con:
                    existing = con.execute("SELECT company_id FROM companies WHERE denue_id=?", (denue_id,)).fetchone() if denue_id else None
                cid = existing[0] if existing else create_company(DB_PATH, name, denue_id=denue_id, state_code=state, municipality=muni)
                st.session_state["radar_selected_company_id"] = cid
                st.success(f"Expediente listo: {cid}")
        else:
            st.info("La corrida actual no expone un campo de nombre reconocible. Puedes cargar una señal manual o revisar el mapeo de columnas.")
        st.info("La interpretación que aparece es una heurística transparente, no una llamada a un LLM. La conexión a un proveedor de IA se incorpora después de validar credenciales y contrato de referencias.")

    with tab_batch:
        st.markdown("### Investigación automatizada por lote")
        st.caption("Busca señales públicas mediante proveedor externo. Los resultados son pistas por revisar, no necesidades confirmadas; no cambian Score ni categorías V3.")
        try:
            tavily_configurada = bool(__import__("os").getenv("TAVILY_API_KEY", "") or st.secrets.get("TAVILY_API_KEY", ""))
        except Exception:
            tavily_configurada = False
        if not tavily_configurada:
            st.warning("Requiere configurar el secreto TAVILY_API_KEY en Streamlit. Si no está disponible, el Radar lo indicará sin simular búsquedas.")
        batch_file = st.file_uploader("Carga CSV AA o VALIDAR", type=["csv"], key="radar_batch_csv")
        if batch_file is not None:
            try:
                batch_df = pd.read_csv(batch_file, dtype=str, encoding="utf-8-sig").fillna("")
                batch_cols = _company_columns(batch_df)
                if not batch_cols.get("name"):
                    st.error("No identifiqué la columna nom_estab/nombre. No se ejecutó ninguna búsqueda.")
                else:
                    st.caption(f"Registros leídos: {len(batch_df):,}. Se permite procesar hasta 20 empresas por corrida.")
                    n = min(20, len(batch_df))
                    limit = st.number_input("Empresas a investigar en este lote", min_value=1, max_value=max(1,n), value=min(10,n), step=1, key="radar_batch_limit")
                    preview = batch_df.head(int(limit))
                    st.dataframe(preview.head(5), use_container_width=True, hide_index=True)
                    if st.button("Buscar señales del lote", key="radar_batch_run"):
                        key = os.getenv("TAVILY_API_KEY", "")
                        try:
                            key = key or st.secrets.get("TAVILY_API_KEY", "")
                        except Exception:
                            pass
                        if not key:
                            st.error("No se ejecutó la búsqueda: falta configurar TAVILY_API_KEY en los secretos de la aplicación.")
                        else:
                            companies=[]
                            for _, row in preview.iterrows():
                                name = str(row.get(batch_cols["name"], "")).strip()
                                if batch_cols.get("razon") and str(row.get(batch_cols["razon"], "")).strip():
                                    name = str(row[batch_cols["razon"]]).strip() or name
                                companies.append({"display_name":name or "Establecimiento sin nombre", "denue_id":str(row.get(batch_cols["id"], "")) if batch_cols.get("id") else "", "state":str(row.get(batch_cols["state"], "")) if batch_cols.get("state") else "", "municipality":str(row.get(batch_cols["municipality"], "")) if batch_cols.get("municipality") else "", "activity":str(row.get(batch_cols["activity"], "")) if batch_cols.get("activity") else ""})
                            results = run_batch(companies, search_fn=lambda c: __import__("radar_batch").search_company_tavily(c, api_key=key), max_batch=20)
                            stored=0; summary=[]
                            for item in results:
                                co=item["company"]
                                summary.append({"Empresa":co["display_name"],"Estado":item["status"],"Señales":item["result_count"],"Error":item["error"] or ""})
                                if item["status"] != "OK": continue
                                denue_id=co.get("denue_id") or None
                                with connect(DB_PATH) as con:
                                    existing=con.execute("SELECT company_id FROM companies WHERE denue_id=?",(denue_id,)).fetchone() if denue_id else None
                                cid=existing[0] if existing else create_company(DB_PATH,co["display_name"],denue_id=denue_id,state_code=co.get("state") or None,municipality=co.get("municipality") or None)
                                for hit in item["results"]:
                                    add_signal(DB_PATH,company_id=cid,source_id=hit["source_id"],source_url=hit["source_url"],signal_type="NOTICIA-CORPORATIVA",title=hit["title"],snippet=hit["snippet"],published_at=hit.get("published_at"),source_status="LOCALIZADA",identity_status=hit["identity_status"],need_hypothesis=hit["need_hypothesis"],next_best_question=hit["next_best_question"],competition_status="INDETERMINADO",run_id=str(metrics.get("run_id","RUN-BATCH")),rule_version=BATCH_RULE_VERSION,payload={"search_query":hit["query"],"heuristic_not_llm":True,"score_impact":0.0,"company_identity_requires_review":True})
                                    stored+=1
                            st.session_state["radar_batch_summary"] = summary
                            st.success(f"Lote terminado. Señales registradas para revisión: {stored}. Score V3 no fue modificado.")
                    if st.session_state.get("radar_batch_summary"):
                        st.dataframe(pd.DataFrame(st.session_state["radar_batch_summary"]), use_container_width=True, hide_index=True)
            except Exception as exc:
                st.error(f"No se pudo leer el CSV: {type(exc).__name__}: {exc}")

    with tab_dossier:
        with connect(DB_PATH) as con:
            companies = con.execute("SELECT * FROM companies ORDER BY created_at DESC").fetchall()
        if not companies:
            st.info("Todavía no hay expedientes. Crea uno desde una empresa V3 o guarda una señal.")
        else:
            options = {f"{c['display_name']} · {c['company_id'][:8]}": c['company_id'] for c in companies}
            chosen = st.selectbox("Expediente", list(options.keys()), key="radar_dossier_select")
            cid = options[chosen]
            dossier = get_company_dossier(DB_PATH, cid)
            co = dossier["company"]
            c1,c2,c3 = st.columns(3); c1.metric("Señales", dossier["signal_count"]); c2.metric("Impacto Score", f"{dossier['score_impact_total']:.1f}"); c3.metric("ID DENUE", co.get("denue_id") or "No vinculado")
            st.write({"Empresa":co["display_name"], "Entidad":co["state_code"], "Municipio":co["municipality"], "CLEE":co.get("denue_clee") or "No vinculada", "Creado":co["created_at"]})
            with st.expander("🔗 Vincular / actualizar identidad oficial DENUE"):
                st.caption("Solo actualiza identificadores y ubicación del expediente seleccionado. No crea empresas, no cambia señales ni modifica Score o pipeline V3.")
                denue_id_input = st.text_input("ID oficial DENUE", value=str(co.get("denue_id") or ""), key=f"denue_id_{cid}")
                denue_clee_input = st.text_input("CLEE oficial", value=str(co.get("denue_clee") or ""), key=f"denue_clee_{cid}")
                if st.button("Validar y vincular DENUE", key=f"link_denue_{cid}"):
                    try:
                        link_company_denue(DB_PATH, cid, denue_id_input, denue_clee_input, state_code="19", municipality="Apodaca")
                        st.success("Identidad DENUE vinculada al expediente existente. No se modificaron señales ni variables de V3.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"No se vinculó el registro: {exc}")
            if dossier["signals"]:
                sig_df = pd.DataFrame(dossier["signals"])
                st.dataframe(sig_df[[c for c in ["signal_id","title","signal_type","source_url","captured_at","human_review_status","need_hypothesis","next_best_question","score_impact"] if c in sig_df]], use_container_width=True, hide_index=True)
                for sig in dossier["signals"]:
                    with st.expander(f"Fuente: {sig['title'][:100]}"):
                        st.markdown(f"[Abrir fuente original]({sig['source_url']})")
                        st.text_area("Contenido de la fuente", sig["snippet"], height=180, key=f"dossier_snippet_{sig['signal_id']}")
                        st.write("**Hipótesis (no validada):**", sig["need_hypothesis"] or "Sin hipótesis")
                        st.write("**Pregunta sugerida:**", sig["next_best_question"] or "Pendiente")
                        st.caption(f"Run_ID: {sig['run_id']} · Rule_Version Radar: {sig['rule_version']} · Impacto Score: {sig['score_impact']}")
            else: st.info("Expediente creado sin señales. El resultado cero también queda registrado al consultar una fuente sin hallazgos.")

    with tab_review:
        with connect(DB_PATH) as con:
            pending = con.execute("SELECT * FROM signals WHERE human_review_status='PENDIENTE' ORDER BY captured_at DESC").fetchall()
        if not pending: st.info("No hay señales pendientes de revisión.")
        else:
            opts = {f"{s['title'][:90]} · {s['signal_id'][:8]}": s['signal_id'] for s in pending}
            label = st.selectbox("Señal pendiente", list(opts.keys()), key="radar_review_signal")
            sig_id = opts[label]
            sig = next(dict(s) for s in pending if s["signal_id"] == sig_id)
            st.markdown(f"[Abrir fuente original]({sig['source_url']})")
            st.text_area("Contenido de la fuente", sig["snippet"], height=180, key="review_snippet")
            st.write("**Hipótesis:**", sig["need_hypothesis"] or "Ninguna")
            with st.form("radar_review_form"):
                status = st.selectbox("Dictamen humano", ["VALIDADA_COMERCIAL", "DESCARTADA", "NO_CONCLUYENTE"])
                reviewer = st.text_input("Revisor / responsable")
                reason = st.text_area("Justificación y evidencia revisada")
                submitted = st.form_submit_button("Registrar revisión")
            if submitted:
                try:
                    review_signal(DB_PATH, sig_id, status, reviewer.strip(), reason.strip())
                    st.success("Revisión registrada con responsable y justificación. El Score V3 no se modificó.")
                    st.rerun()
                except Exception as exc: st.error(str(exc))
