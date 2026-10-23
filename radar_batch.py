"""Batch evidence discovery for CONCEDE Radar. Requires explicit Tavily API key.
Signals are research leads, not confirmed needs; never touches V3 scoring.
"""
from __future__ import annotations
import json, os
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from radar_logic import hypothesis_from_text, commercial_relevance

RULE_VERSION = "RADAR-BATCH-0.2.0"
MAX_BATCH = 20

class RadarProviderError(RuntimeError):
    pass

def search_company_tavily(company: dict, api_key: str | None = None, timeout: int = 20) -> list[dict]:
    """Search public web for one company. Requires TAVILY_API_KEY; no silent fallback."""
    key = api_key or os.getenv("TAVILY_API_KEY")
    if not key:
        raise RadarProviderError("Falta TAVILY_API_KEY. Configure el secreto antes de ejecutar búsquedas por lote.")
    name = str(company.get("display_name") or "").strip()
    if not name:
        raise ValueError("La empresa necesita nombre para construir la búsqueda.")
    state = str(company.get("state") or "").strip()
    municipality = str(company.get("municipality") or "").strip()
    activity = str(company.get("activity") or "").strip()
    query = " ".join(x for x in [f'"{name}"', municipality, state, activity,
        "expansión OR inversión OR vacantes OR logística OR almacén OR distribución OR proyecto"] if x)
    payload = {"api_key": key, "query": query, "topic": "general", "search_depth": "basic", "max_results": 5,
               "include_answer": False, "include_raw_content": False}
    req = Request("https://api.tavily.com/search", data=json.dumps(payload).encode(),
                  headers={"Content-Type":"application/json", "Accept":"application/json"}, method="POST")
    try:
        with urlopen(req, timeout=timeout) as response:
            data=json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RadarProviderError(f"Fallo de búsqueda para {name}: {type(exc).__name__}: {exc}") from exc
    results=[]
    for item in data.get("results", []):
        url=str(item.get("url") or "")
        parsed=urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            continue
        title=str(item.get("title") or "Sin título")[:300]
        content=str(item.get("content") or "")[:3500]

        # Reject irrelevant search noise before it becomes a dossier signal.
        relevant, relevance_reason = commercial_relevance(title, content, url)
        if not relevant:
            continue

        hypothesis, question = hypothesis_from_text(title + " " + content, "NOTICIA-CORPORATIVA")
        results.append({"source_id":"TAVILY_WEB_SEARCH", "source_url":url, "title":title,
                        "snippet":content, "published_at":item.get("published_date"),
                        "need_hypothesis":hypothesis, "next_best_question":question,
                        "score_impact":0.0, "human_review_status":"PENDIENTE",
                        "identity_status":"PENDIENTE_REVISION", "query":query,
                        "relevance_status":"ACEPTADA", "relevance_reason":relevance_reason})
    return results

def run_batch(companies: list[dict], search_fn=search_company_tavily, max_batch: int=MAX_BATCH) -> list[dict]:
    """Process a small explicit batch. Errors are returned per company, never hidden."""
    if len(companies) > max_batch:
        raise ValueError(f"Lote de {len(companies)} excede el máximo seguro de {max_batch}; dividir el lote.")
    output=[]
    for company in companies:
        try:
            hits=search_fn(company)
            output.append({"company":company, "status":"OK", "result_count":len(hits), "results":hits, "error":None})
        except Exception as exc:
            output.append({"company":company, "status":"ERROR", "result_count":0, "results":[], "error":f"{type(exc).__name__}: {exc}"})
    return output
