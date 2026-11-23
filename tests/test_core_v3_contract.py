import json
from pathlib import Path

import pandas as pd
import pytest

from core import ConfigError, load_config, run

ROOT = Path(__file__).resolve().parents[1]
CFG = load_config(ROOT / "concede_v3.json")


def sample_base():
    return pd.DataFrame([
        {"id": "A-001", "nombre_act": "Almacenamiento y logística", "per_ocu": "31 a 50 personas", "entidad": "NUEVO LEÓN"},
        {"id": "A-002", "nombre_act": "Comercio al por mayor de alimentos", "per_ocu": "51 a 100 personas", "entidad": "NUEVO LEÓN"},
    ])


def test_v3_rejects_global_need_evidence():
    with pytest.raises(ConfigError, match="asociarse por empresa"):
        run(
            sample_base(), CFG, ["NUEVO LEÓN"],
            need_evidence={"almacenamiento": 100, "flota": 100, "tecnologia": 100, "urgencia": 100},
        )


def test_v3_applies_need_evidence_only_to_matching_company_id():
    result, metrics = run(
        sample_base(), CFG, ["NUEVO LEÓN"],
        need_evidence_by_id={
            "A-001": {"almacenamiento": 100, "flota": 50, "tecnologia": 75, "urgencia": 25}
        },
    )
    scores = result.set_index("id")["Score_Necesidad"].to_dict()
    assert scores["A-001"] == 62.5
    assert scores["A-002"] == 0.0
    assert metrics["raw"] == 2


def test_v3_requires_stable_id_for_company_level_evidence():
    base = sample_base().drop(columns=["id"])
    with pytest.raises(ConfigError, match="columna ID reconocible"):
        run(
            base, CFG, ["NUEVO LEÓN"],
            need_evidence_by_id={"A-001": {"almacenamiento": 100, "flota": 100, "tecnologia": 100, "urgencia": 100}},
        )


def test_v3_rejects_invalid_need_evidence_values():
    with pytest.raises(ConfigError, match="Valor de necesidad inválido"):
        run(
            sample_base(), CFG, ["NUEVO LEÓN"],
            need_evidence_by_id={"A-001": {"almacenamiento": 90, "flota": 100, "tecnologia": 100, "urgencia": 100}},
        )
