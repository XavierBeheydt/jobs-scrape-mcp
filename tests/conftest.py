import pytest
from jobs_scrape import storage
from jobs_scrape.items import JobItem, compute_fingerprint


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    """Une base peuplee, isolee du disque de developpement."""
    db = tmp_path / "jobs.db"
    monkeypatch.setenv("JOBS_SCRAPE_DB", str(db))

    conn = storage.connect(db)
    offres = [
        dict(source="jobroom", external_id="1", url="https://a/1",
             title="Développeur Python senior", company="ACME SA",
             description="Django, PostgreSQL et Kubernetes au quotidien. " * 30,
             city="Genève", region="GE", country="CH", lang="fr",
             skills=["python", "django", "kubernetes"], keywords=["backend"],
             workload_min=80, workload_max=100, posted_at="2026-08-20",
             seniority="senior", remote_policy="hybride", contract_type="permanent"),
        dict(source="jobroom", external_id="2", url="https://a/2",
             title="Pflegefachfrau HF", company="Spital ZH",
             description="Geriatrie und Demenzbetreuung.",
             city="Zürich", region="ZH", country="CH", lang="de",
             skills=["soins_infirmiers", "geriatrie"],
             workload_min=100, workload_max=100, posted_at="2026-08-19"),
        dict(source="apec", external_id="3", url="https://b/3",
             title="Chef de projet informatique", company="Conseil FR",
             description="Pilotage de projets, méthode agile.",
             city="Lyon", region="69", country="FR", lang="fr",
             skills=["gestion_projet", "agile"], posted_at="2026-08-18",
             salary_min=45000.0, salary_max=55000.0, salary_currency="EUR"),
    ]
    for values in offres:
        item = JobItem(**values)
        item.fingerprint = compute_fingerprint(item)
        storage.upsert(conn, item)
    conn.commit()
    conn.close()
    return db


@pytest.fixture
def base_vide(tmp_path, monkeypatch):
    db = tmp_path / "vide.db"
    monkeypatch.setenv("JOBS_SCRAPE_DB", str(db))
    storage.connect(db).close()
    return db
