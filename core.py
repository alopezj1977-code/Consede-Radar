import json, unicodedata
from pathlib import Path
from datetime import datetime
import pandas as pd

class ConfigError(ValueError):
    pass

REQUIRED_TOP = ["motor","run","eligibility","sector","size","geography","need","capacity_own","score","priority","pipeline","crm"]

# Catálogo explícito INEGI/entidad federativa -> clave cve_ent.
STATE_CODE_MAP = {
    "01":"AGUASCALIENTES","02":"BAJA CALIFORNIA","03":"BAJA CALIFORNIA SUR","04":"CAMPECHE",
    "05":"COAHUILA","06":"COLIMA","07":"CHIAPAS","08":"CHIHUAHUA","09":"CIUDAD DE MÉXICO",
    "10":"DURANGO","11":"GUANAJUATO","12":"GUERRERO","13":"HIDALGO","14":"JALISCO",
    "15":"ESTADO DE MÉXICO","16":"MICHOACÁN","17":"MORELOS","18":"NAYARIT","19":"NUEVO LEÓN",
    "20":"OAXACA","21":"PUEBLA","22":"QUERÉTARO","23":"QUINTANA ROO","24":"SAN LUIS POTOSÍ",
    "25":"SINALOA","26":"SONORA","27":"TABASCO","28":"TAMAULIPAS","29":"TLAXCALA",
    "30":"VERACRUZ","31":"YUCATÁN","32":"ZACATECAS",
}


def normalize(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = str(value).strip().lower()
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").upper()


def normalize_state_code(value):
    n = normalize(value)
    if not n:
        return ""
    # DENUE normalmente entrega 01..32; toleramos 1..32 sin introducir heurística geográfica.
    try:
        i = int(float(n))
        if 1 <= i <= 32:
            return f"{i:02d}"
    except Exception:
        pass
    return n if n in STATE_CODE_MAP else ""


def load_config(path):
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    miss = [k for k in REQUIRED_TOP if k not in cfg]
    if miss:
        raise ConfigError(f"Configuración incompleta; faltan: {miss}")
    if cfg["run"].get("no_silent_fallbacks") is not True:
        raise ConfigError("V3 exige no_silent_fallbacks=true")
    if len(cfg["geography"]["entities"]) != 32:
        raise ConfigError("El catálogo debe contener exactamente 32 entidades")
    if round(sum(cfg["score"]["weights"].values()), 6) != 100:
        raise ConfigError("Los pesos Score V3 deben sumar 100")
    if "ticket_promedio_mxn" not in cfg["pipeline"]:
        raise ConfigError("Falta ticket_promedio_mxn")
    return cfg


ALIASES = {
    "id":["id"],
    "nom_estab":["nom_estab","nombre","empresa","nombre_establecimiento","establecimiento","nombre comercial"],
    "raz_social":["raz_social","razon social","razon_social","empresa_razon"],
    "nombre_act":["nombre_act","actividad","giro","sector","rama","actividad_economica"],
    "per_ocu":["per_ocu","empleados","tamano","tamaño","personal","estrato_personal","rango_empleados"],
    "entidad":["entidad","estado","ubicacion","region","entidad_federativa"],
    "cve_ent":["cve_ent","clave_entidad","clave_ent","cve_entidad"],
    "municipio":["municipio"],
}


def identify_columns(df):
    norm = {normalize(c): c for c in df.columns}
    out = {}
    for std, als in ALIASES.items():
        out[std] = next((norm[normalize(a)] for a in als if normalize(a) in norm), None)
    return out


def required_columns(mapping):
    return [x for x in ["nombre_act","per_ocu","entidad"] if not mapping.get(x)]


def canonical_entity(value, cfg):
    """Normalización explícita de nombres de entidad; sin coincidencias parciales."""
    n = normalize(value)
    aliases = cfg.get("geography", {}).get("entity_aliases", {})
    alias_map = {normalize(k): normalize(v) for k, v in aliases.items()}
    return alias_map.get(n, n)


def canonical_from_code(value, cfg):
    code = normalize_state_code(value)
    if code in STATE_CODE_MAP:
        return normalize(STATE_CODE_MAP[code])
    return ""


def canonical_source_entity(name_value, code_value, cfg):
    """Prioriza cve_ent oficial cuando existe; usa el nombre solo si la clave no está disponible."""
    by_code = canonical_from_code(code_value, cfg)
    if by_code:
        return by_code
    return canonical_entity(name_value, cfg)


def size_bucket(value):
    s = normalize(value)
    if "0 A 5" in s or "0-5" in s or "1 A 5" in s: return "0-5"
    if "6 A 10" in s or "6-10" in s: return "6-10"
    if "11 A 30" in s or "11-30" in s: return "11-30"
    if "31 A 50" in s or "31-50" in s: return "31-50"
    if "51 A 100" in s or "51-100" in s: return "51-100"
    if "101 A 250" in s or "101-250" in s: return "101-250"
    if "251" in s: return "251+"
    try:
        n = float(value)
        return "0-5" if n <= 5 else "6-10" if n <= 10 else "11-30" if n <= 30 else "31-50" if n <= 50 else "51-100" if n <= 100 else "101-250" if n <= 250 else "251+"
    except Exception:
        return None


def size_lower_bound(bucket):
    return {"0-5":0,"6-10":6,"11-30":11,"31-50":31,"51-100":51,"101-250":101,"251+":251}.get(bucket)


def size_upper_bound(bucket):
    return {"0-5":5,"6-10":10,"11-30":30,"31-50":50,"51-100":100,"101-250":250,"251+":float("inf")}.get(bucket)


def eligible(value, minimum, maximum=None):
    b = size_bucket(value)
    if b is None: return False
    lo = size_lower_bound(b); hi = size_upper_bound(b)
    if lo < minimum: return False
    if maximum is not None and hi > maximum: return False
    return True


def classify_sector(activity, cfg):
    txt = normalize(activity)
    if not txt: return "Otro"
    if any(normalize(x) in txt for x in cfg["sector"]["direct_excluders"]): return "Otro"
    for sector, keys in cfg["sector"]["taxonomy"].items():
        if any(normalize(x) in txt for x in keys): return sector
    return "Otro"


def score_need(evidence, cfg):
    if not evidence: return 0.0
    vals = []
    for key in ["almacenamiento","flota","tecnologia","urgencia"]:
        v = evidence.get(key, 0)
        if v not in cfg["need"]["scale"]:
            raise ConfigError(f"Valor de necesidad inválido en {key}: {v}")
        vals.append(float(v))
    return sum(vals) / 4


def priority_band(score, bands):
    for b in bands:
        if b["min"] <= score <= b["max"]: return b["code"]
    raise ConfigError(f"Score fuera de rango: {score}")


def run(df, cfg, selected_entities, run_id=None, need_evidence=None, employee_minimum=None, employee_maximum=None, need_evidence_by_id=None):
    if not selected_entities:
        raise ConfigError("Debe seleccionarse al menos una entidad o TODAS LAS ENTIDADES.")
    valid = set(cfg["geography"]["entities"])
    selected = [e for e in selected_entities if e != "TODAS LAS ENTIDADES"]
    unknown = [e for e in selected if e not in valid]
    if unknown:
        raise ConfigError(f"Entidades no válidas: {unknown}")
    mp = identify_columns(df)
    missing = required_columns(mp)
    if missing:
        raise ConfigError(f"Faltan campos indispensables: {missing}")
    rid = run_id or datetime.now().strftime("CONCEDE-%Y%m%d-%H%M%S")
    res = df.copy(); res["Run_ID"] = rid; res["Rule_Version"] = cfg["motor"]["version"]
    emp, act, geo, code = mp["per_ocu"], mp["nombre_act"], mp["entidad"], mp.get("cve_ent")
    min_emp = cfg["eligibility"]["employee_minimum"] if employee_minimum is None else employee_minimum
    max_emp = cfg["eligibility"].get("employee_maximum") if employee_maximum is None else employee_maximum
    if min_emp is None or min_emp < 0: raise ConfigError("employee_minimum inválido")

    res["Estrato_Tamano"] = res[emp].apply(size_bucket)
    if res["Estrato_Tamano"].isna().any(): raise ConfigError("Existe estrato de tamaño no reconocido; no hay fallback silencioso")
    res["Elegible"] = res[emp].apply(lambda x: eligible(x, min_emp, max_emp))

    all_selected = (not selected) or len(selected) == 32
    selected_norm = {canonical_entity(x, cfg) for x in selected}

    if code and code in res.columns:
        res["Entidad_CANONICA"] = [canonical_source_entity(n, c, cfg) for n, c in zip(res[geo], res[code])]
        res["Entidad_Fuente"] = res[geo].astype(str)
        res["CVE_ENT_Fuente"] = res[code].astype(str)
    else:
        res["Entidad_CANONICA"] = res[geo].apply(lambda x: canonical_source_entity(x, None, cfg))
        res["Entidad_Fuente"] = res[geo].astype(str)
        res["CVE_ENT_Fuente"] = ""

    res["Target_Geografico"] = True if all_selected else res["Entidad_CANONICA"].isin(selected_norm)
    res["Score_Geografia"] = float(cfg["geography"]["selected_score"]) if all_selected else res["Entidad_CANONICA"].apply(lambda x: float(cfg["geography"]["selected_score"]) if x in selected_norm else float(cfg["geography"]["not_selected_score"]))

    res["Sector_Comercial"] = res[act].apply(lambda x: classify_sector(x, cfg))
    affinity = {normalize(x) for x in cfg["sector"]["affinity_sectors"]}
    res["Score_Sector"] = res["Sector_Comercial"].apply(lambda x: float(cfg["sector"]["match_score"]) if normalize(x) in affinity else float(cfg["sector"]["no_match_score"]))
    res["Score_Tamano"] = res["Estrato_Tamano"].map(cfg["size"]["scores"])
    if res["Score_Tamano"].isna().any(): raise ConfigError("Estrato sin puntuación configurada; no hay fallback silencioso")
    # Evidencia comercial individual por establecimiento: nunca propagar una señal de una empresa a toda la base.
    if need_evidence_by_id is not None:
        id_col = mp.get("id")
        if not id_col:
            raise ConfigError("need_evidence_by_id requiere una columna ID reconocible; no hay fallback por posición")
        evidence_map = need_evidence_by_id
        res["Score_Necesidad"] = res[id_col].apply(
            lambda company_id: float(score_need(evidence_map.get(str(company_id)), cfg))
        )
    else:
        # No permitir evidencia global de lote: puede contaminar la puntuación
        # de empresas sin evidencia propia. La evidencia debe asociarse a ID estable.
        if need_evidence is not None:
            raise ConfigError("La evidencia de necesidad debe asociarse por empresa mediante need_evidence_by_id; se rechaza evidencia global")
        res["Score_Necesidad"] = 0.0
    w = cfg["score"]["weights"]
    res["Score_V3"] = res["Score_Sector"]*w["sector"]/100 + res["Score_Tamano"]*w["size"]/100 + res["Score_Geografia"]*w["geography"]/100 + res["Score_Necesidad"]*w["need"]/100
    res["Prioridad"] = res["Score_V3"].apply(lambda x: priority_band(x, cfg["priority"]["bands"]))
    res["Capacidad_Propia"] = "CAP-00 DESCONOCIDA"; res["CRM_Estado"] = "PROSPECTO"
    res["Candidato_Comercial"] = res["Elegible"] & res["Target_Geografico"]

    aaa = int(((res["Prioridad"] == "AAA") & res["Candidato_Comercial"]).sum())
    ticket = float(cfg["pipeline"]["ticket_promedio_mxn"]); valor = aaa * ticket
    return res, {
        "run_id": rid,
        "raw": len(res),
        "eligible": int(res["Elegible"].sum()),
        "target_geography": int(res["Target_Geografico"].sum()),
        "commercial_candidates": int(res["Candidato_Comercial"].sum()),
        "aaa": aaa,
        "aa": int(((res["Prioridad"] == "AA") & res["Candidato_Comercial"]).sum()),
        "validar": int(((res["Prioridad"] == "VALIDAR") & res["Candidato_Comercial"]).sum()),
        "valor_potencial": valor,
        "ticket_promedio_mxn": ticket,
    }
