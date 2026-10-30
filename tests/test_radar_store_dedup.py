import pytest

from radar_store import add_signal, connect, create_company


def _add(db_path, company_id, url="https://example.com/news/1", return_created=False):
    return add_signal(
        db_path,
        company_id=company_id,
        source_id="TAVILY_WEB_SEARCH",
        source_url=url,
        signal_type="NOTICIA-CORPORATIVA",
        title="Noticia de expansión",
        snippet="Contenido de prueba",
        run_id="RUN-TEST",
        rule_version="RADAR-TEST",
        return_created=return_created,
    )


def test_same_company_source_url_is_not_inserted_twice(tmp_path):
    db = tmp_path / "radar.sqlite3"
    company = create_company(db, "Empresa Uno", denue_id="100")
    first_id, first_created = _add(db, company, return_created=True)
    second_id, second_created = _add(db, company, return_created=True)
    assert first_id == second_id
    assert first_created is True
    assert second_created is False
    with connect(db) as con:
        assert con.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 1


def test_same_url_for_different_companies_remains_distinct(tmp_path):
    db = tmp_path / "radar.sqlite3"
    company_a = create_company(db, "Empresa A", denue_id="101")
    company_b = create_company(db, "Empresa B", denue_id="102")
    id_a, created_a = _add(db, company_a, return_created=True)
    id_b, created_b = _add(db, company_b, return_created=True)
    assert id_a != id_b
    assert created_a is True and created_b is True
    with connect(db) as con:
        assert con.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 2


def test_unlinked_signal_is_idempotent(tmp_path):
    db = tmp_path / "radar.sqlite3"
    first_id, first_created = _add(db, None, return_created=True)
    second_id, second_created = _add(db, None, return_created=True)
    assert first_id == second_id
    assert first_created is True
    assert second_created is False
    with connect(db) as con:
        assert con.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 1
