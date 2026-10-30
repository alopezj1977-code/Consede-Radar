"""Batch evidence discovery for CONCEDE Radar. Requires explicit Tavily API key.
Signals are research leads, not confirmed needs; never touches V3 scoring.
"""
from __future__ import annotations
import json, os
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from radar_logic import hypothesis_from_text, commercial_relevance
RULE_VERSION = "RADAR-BATCH-0.3.0"
MAX_BATCH = 20
class RadarProviderError(RuntimeError):
    pass
class SearchResults(list):
    """List-compatible results with transparent provider/filter diagnostics."""
    def __init__(self, values=(), diagnostics=None):
        super().__init__(values)
        self.diagnostics = diagnostics or {}
def _company_search_names(company: dict) -> list[str]:
    names, seen = [], set()
    for value in (company.get("display_name"), company.get("legal_name"), company.get("razon_social")):
        name = str(value or "").strip()
        if name and name.casefold() not in seen:
            names.append(name); seen.add(name.casefold())
    return names
def search_company_tavily(company: dict, api_key: str | None = None, timeout: int = 20) -> list[dict]:
    """Search public web for one company; return accepted leads plus diagnostic counters."""
    key = api_key or os.getenv("TAVILY_API_KEY")
    if not key:
        raise RadarProviderError("Falta TAVILY_API_KEY. Configure el secreto antes de ejecutar búsquedas por lote.")
    names = _company_search_names(company)
    if not names:
        raise ValueError("La empresa necesita nombre comercial o razón social para construir la búsqueda.")
    state=str(company.get("state") or "").strip(); municipality=str(company.get("municipality") or "").strip()
    activity=str(company.get("activity") or "").strip()
    identity_query=" OR ".join(f'"{name}"' for name in names)
    query=" ".join(x for x in [f"({identity_query})",municipality,state,activity,
        "empresa OR agroindustria OR exportación OR empaque OR procesamiento OR inversión OR expansión OR vacantes OR logística OR almacén OR distribución OR proyecto"] if x)
    payload={"query":query,"topic":"general","search_depth":"basic","max_results":8,"include_answer":False,"include_raw_content":False}
    req=Request("https://api.tavily.com/search",data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type":"application/json","Accept":"application/json","Authorization":f"Bearer {key}"},method="POST")
    try:
        with urlopen(req,timeout=timeout) as response:
            data=json.loads(response.read().decode("utf-8"))
    except (HTTPError,URLError,TimeoutError,json.JSONDecodeError) as exc:
        detail=getattr(exc,"reason",None) or str(exc)
        raise RadarProviderError(f"Fallo de búsqueda para {' / '.join(names)}: {type(exc).__name__}: {detail}") from exc
    if not isinstance(data,dict) or "results" not in data or not isinstance(data.get("results"),list):
        detail=(data.get("message") or data.get("error")) if isinstance(data,dict) else "respuesta no es un objeto JSON"
        raise RadarProviderError(f"Respuesta inesperada de Tavily: {str(detail or 'no contiene lista results')[:400]}")
    raw_count=len(data["results"]); accepted=[]; rejected={}; invalid_urls=0
    for item in data["results"]:
        if not isinstance(item,dict):
            rejected["REGISTRO_INVALIDO"]=rejected.get("REGISTRO_INVALIDO",0)+1; continue
        source_url=str(item.get("url") or ""); parsed=urlparse(source_url)
        if parsed.scheme!="https" or not parsed.hostname:
            invalid_urls+=1; continue
        title=str(item.get("title") or "Sin título")[:300]; content=str(item.get("content") or "")[:3500]
        relevant,reason=commercial_relevance(title,content,source_url)
        if not relevant:
            rejected[reason]=rejected.get(reason,0)+1; continue
        hypothesis,question=hypothesis_from_text(title+" "+content,"NOTICIA-CORPORATIVA")
        accepted.append({"source_id":"TAVILY_WEB_SEARCH","source_url":source_url,"title":title,"snippet":content,
            "published_at":item.get("published_date"),"need_hypothesis":hypothesis,"next_best_question":question,
            "score_impact":0.0,"human_review_status":"PENDIENTE","identity_status":"PENDIENTE_REVISION",
            "query":query,"relevance_status":"ACEPTADA","relevance_reason":reason})
    diagnostics={"raw_count":raw_count,"accepted_count":len(accepted),"discarded_count":raw_count-len(accepted),
        "invalid_url_count":invalid_urls,"discard_reasons":rejected,"searched_names":names}
    return SearchResults(accepted,diagnostics=diagnostics)
def run_batch(companies: list[dict], search_fn=search_company_tavily, max_batch: int=MAX_BATCH) -> list[dict]:
    """Process a small explicit batch. Empty and discarded results are not reported as success."""
    if len(companies)>max_batch:
        raise ValueError(f"Lote de {len(companies)} excede el máximo seguro de {max_batch}; dividir el lote.")
    output=[]
    for company in companies:
        try:
            hits=search_fn(company); diag=getattr(hits,"diagnostics",{}) or {}
            accepted=len(hits); raw=int(diag.get("raw_count",accepted)); discarded=int(diag.get("discarded_count",max(0,raw-accepted)))
            status="OK" if accepted else ("RESULTADOS_DESCARTADOS" if raw else "SIN_RESULTADOS")
            output.append({"company":company,"status":status,"result_count":accepted,"raw_count":raw,
                "discarded_count":discarded,"diagnostics":diag,"results":list(hits),"error":None})
        except Exception as exc:
            output.append({"company":company,"status":"ERROR","result_count":0,"raw_count":0,
                "discarded_count":0,"diagnostics":{},"results":[],"error":f"{type(exc).__name__}: {exc}"})
    return output
