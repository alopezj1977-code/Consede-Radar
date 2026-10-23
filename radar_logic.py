"""Pure, auditable Radar helpers. No V3 scoring imports."""
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from html.parser import HTMLParser

class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(); self.in_title = False; self.title_parts=[]; self.parts=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"): self.skip += 1
        if tag == "title": self.in_title = True
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip: self.skip -= 1
        if tag == "title": self.in_title = False
    def handle_data(self, data):
        t = " ".join(data.split())
        if not t or self.skip: return
        if self.in_title: self.title_parts.append(t)
        elif len(t) > 35: self.parts.append(t)

def fetch_official_page(url: str, expected_domain: str) -> dict:
    """Recupera contenido oficial con TLS validado y respaldo Tavily expl?cito."""
    import json
    import os
    import re
    import ssl
    from urllib.error import HTTPError, URLError

    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != expected_domain:
        raise ValueError("La URL debe ser HTTPS y pertenecer al dominio oficial seleccionado.")

    direct_error = None
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; CONCEDE-RADAR/0.1)"})
    try:
        with urlopen(req, timeout=12) as resp:
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status} en la fuente oficial")
            raw = resp.read(2_000_000)
            charset = resp.headers.get_content_charset() or "utf-8"
        parser = _TextExtractor()
        parser.feed(raw.decode(charset, errors="replace"))
        title = " ".join(parser.title_parts).strip() or url
        text = " ".join(parser.parts).strip()
        if text:
            return {"title": title[:300], "snippet": text[:3500], "url": url}
        direct_error = RuntimeError("La fuente oficial respondi? sin contenido textual")
    except (HTTPError, URLError, ssl.SSLError, TimeoutError, OSError, RuntimeError) as exc:
        direct_error = exc

    key = os.getenv("TAVILY_API_KEY", "")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("TAVILY_API_KEY", "")
        except Exception:
            pass
    if not key:
        raise RuntimeError(f"No se pudo recuperar la fuente oficial ({direct_error}); TAVILY_API_KEY no est? configurada")

    payload = {"api_key": key, "urls": [url]}
    extract_req = Request(
        "https://api.tavily.com/extract",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(extract_req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError, ssl.SSLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Fall? la fuente oficial ({direct_error}) y tambi?n Tavily Extract ({exc})") from exc

    results = data.get("results", [])
    item = next(
        (r for r in results if urlparse(r.get("url", "")).hostname == expected_domain),
        None,
    )
    if not item:
        failed = data.get("failed_results", [])
        detail = failed[0].get("error", "sin contenido recuperado") if failed else "sin resultados"
        raise RuntimeError(f"La fuente oficial fall? ({direct_error}); Tavily no recuper? contenido: {detail}")

    text = (item.get("raw_content") or item.get("content") or "").strip()
    if not text:
        raise RuntimeError("Tavily respondi?, pero no devolvi? contenido textual verificable")
    title_match = re.search(r"(?m)^#+\\s+(.+)$", text)
    title = title_match.group(1).strip() if title_match else (item.get("title") or url)
    return {"title": title[:300], "snippet": text[:3500], "url": url}


# Radar relevance gate: conservative by design. A result must contain an
# explicit business/operational trigger and must not be clearly off-topic.
import re
import unicodedata

_OFF_TOPIC_PATTERNS = (
    r"\bhoroscop\w*\b", r"\bzodiac\w*\b", r"\bastrolog\w*\b",
    r"\bcrossword\w*\b", r"\bcrucigrama\w*\b", r"\bpuzzle\w*\b",
    r"\bwordle\b", r"\breceta\w*\b", r"\brecipe\w*\b",
    r"\bpronostico del tiempo\b", r"\bweather forecast\b",
    r"\bcelebrity gossip\b", r"\bfamosos\b", r"\bchisme\w*\b",
    r"\bresultados? deportivos?\b", r"\bsports scores?\b",
)

_BUSINESS_TRIGGER_PATTERNS = (
    r"\bexpansion\b", r"\bexpand\w*\b", r"\binversion\b", r"\binvestment\w*\b",
    r"\bnueva planta\b", r"\bnew plant\b", r"\binaugur\w*\b",
    r"\bcentros? de distribucion\b", r"\bdistribution center\b",
    r"\bcentros? logisticos?\b", r"\blogistics hub\b",
    r"\balmacenes?\b", r"\bwarehouses?\b",
    r"\bcontratacion\b", r"\bhiring\b", r"\bvacantes?\b", r"\bjob openings?\b",
    r"\blicitaciones?\b", r"\btenders?\b", r"\bcontratos? adjudicados?\b",
    r"\bcontract awards?\b", r"\blicencias? de construccion\b",
    r"\bconstruction permits?\b", r"\bconstruccion de\b", r"\bconstruye(n|ndo)?\b",
    r"\bflota\b", r"\bfleet\b", r"\btransporte\b", r"\btransportation\b",
    r"\bcadena de suministro\b", r"\bsupply chain\b", r"\boperaciones logisticas?\b",
    r"\bproyectos? industriales?\b", r"\bparque industrial\b",
    r"\bcompra de\b.{0,40}\bterrenos?\b", r"\bcompra de\b.{0,40}\binmuebles?\b",
)

def _normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or "").lower())
    return "".join(ch for ch in value if not unicodedata.combining(ch))

def commercial_relevance(title: str, snippet: str = "", url: str = "") -> tuple[bool, str]:
    """Filtro conservador de relevancia comercial; no confirma necesidades."""
    text = _normalize_text(" ".join((title or "", snippet or "", url or "")))

    for pattern in _OFF_TOPIC_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return False, "CONTENIDO_FUERA_DE_TEMA"

    business_patterns = (
        r"\bexpansion(?:es)?\b",
        r"\binversion(?:es)?\b",
        r"\b(?:inaugura|inauguracion|construccion|apertura)\b",
        r"\b(?:nueva|nuevas|nuevo|nuevos)\s+plantas?\b",
        r"\bplantas?\s+(?:industrial|industriales|de produccion)\b",
        r"\bcentros?\s+de\s+distribucion\b",
        r"\bcentros?\s+logisticos?\b",
        r"\b(?:almacen|almacenes|bodegas|warehouses?)\b",
        r"\b(?:contratacion|vacantes|empleo|job openings)\b",
        r"\blicitacion(?:es)?\b",
        r"\bcontratos?\s+(?:adjudicados?|publicos?)\b",
        r"\bconcursos?\s+publicos?\b",
        r"\b(?:servicios|soluciones|proyectos?)\s+tecnologicos?\b",
        r"\btransformacion\s+digital\b",
        r"\bimplementacion\s+de\s+(?:software|sistemas|erp|tecnologia)\b",
        r"\badquisicion\s+de\s+(?:software|sistemas|tecnologia)\b",
        r"\b(?:infraestructura|modernizacion)\s+tecnologica\b",
        r"\b(?:flota|transporte|cadena\s+de\s+suministro|operaciones\s+logisticas)\b",
        r"\b(?:parque|proyecto)\s+industrial\b",
        r"\b(?:compra|adquisicion)\s+de\s+(?:terrenos|inmuebles)\b",
    )

    if any(re.search(p, text, flags=re.IGNORECASE) for p in business_patterns):
        return True, "INDICIO_COMERCIAL_EXPLICITO"

    return False, "SIN_INDICIO_COMERCIAL_EXPLICITO"


def hypothesis_from_text(text: str, signal_type: str) -> tuple[str, str]:
    """Transparent heuristic, not an LLM: creates a question, never a confirmed need."""
    t = (text or "").lower()
    clues = []
    for words, label in [
        (("planta", "inaugur", "expansi", "inversión", "inversion", "parque industrial"), "posible expansión o cambio operativo"),
        (("almacén", "almacen", "logística", "logistica", "distribución", "distribucion"), "posible actividad de almacenamiento o distribución"),
        (("vacante", "empleo", "contratación", "contratacion", "operador"), "posible cambio de capacidad operativa o contratación"),
        (("licencia", "construcción", "construccion", "permiso"), "posible actividad de obra o instalación"),
    ]:
        if any(w in t for w in words): clues.append(label)
    if clues:
        hypothesis = "Hipótesis no validada: la fuente podría indicar " + "; ".join(dict.fromkeys(clues)) + "."
    else:
        hypothesis = "No hay evidencia textual suficiente para formular una hipótesis específica; conservar como señal pendiente."
    question = "¿Este proyecto o cambio operativo genera necesidades actuales de transporte, almacenamiento o distribución que CONSEDE pueda atender?"
    return hypothesis, question
