"""Outils MCP : contrat de sortie, filtres, et maitrise du volume."""

import pytest

from jobs_scrape_mcp.server import (
    SNIPPET,
    get_job,
    list_facets,
    list_sources,
    search_jobs,
    stats,
    timeline,
    top_skills,
)

# -- recherche ---------------------------------------------------------


def test_recherche_plein_texte(corpus):
    result = search_jobs(query="python")
    assert result["total"] == 1
    assert result["jobs"][0]["title"] == "Développeur Python senior"


def test_recherche_sans_accent(corpus):
    """Personne ne tape les accents dans une barre de recherche."""
    assert search_jobs(query="developpeur")["total"] == 1


def test_recherche_sans_terme_parcourt(corpus):
    """Sans requete, l'outil sert a parcourir : les plus recentes d'abord."""
    result = search_jobs()
    assert result["total"] == 3
    assert result["jobs"][0]["posted_at"] == "2026-08-20"


@pytest.mark.parametrize("filtre,valeur,attendu", [
    ("region", "GE", 1),
    ("region", "ZH", 1),
    ("source", "apec", 1),
    ("city", "Gen", 1),          # appariement partiel
    ("company", "ACME", 1),
    ("remote_policy", "hybride", 1),
    ("contract_type", "permanent", 1),
    ("workload_min", 90, 2),
    ("salary_min", 40000, 1),
    ("posted_since", "2026-08-19", 2),
])
def test_filtres(corpus, filtre, valeur, attendu):
    assert search_jobs(**{filtre: valeur})["total"] == attendu


def test_filtre_competences_cumulatif(corpus):
    assert search_jobs(skills=["python"])["total"] == 1
    assert search_jobs(skills=["python", "django"])["total"] == 1
    assert search_jobs(skills=["python", "cobol"])["total"] == 0


def test_limite_bornee(corpus):
    """Une limite absurde ne doit pas inonder le contexte du modele."""
    assert search_jobs(limit=9999)["returned"] <= 50
    assert search_jobs(limit=0)["returned"] >= 1
    assert search_jobs(limit=1)["returned"] == 1


def test_les_extraits_sont_tronques(corpus):
    """Rendre vingt descriptions completes saturerait le contexte pour rien."""
    job = search_jobs(query="python")["jobs"][0]
    assert len(job["excerpt"]) <= SNIPPET + 1
    assert job["excerpt"].endswith("…")
    assert "description" not in job


def test_total_distinct_du_nombre_rendu(corpus):
    """Le modele doit savoir qu'il ne voit qu'une partie des correspondances."""
    result = search_jobs(limit=1)
    assert result["total"] == 3
    assert result["returned"] == 1


def test_saisie_hostile_ne_plante_pas(corpus):
    for query in ['python "chef de projet"', "c++ (dev)", 'guillemet " seul', "*", "^^^"]:
        search_jobs(query=query)


def test_absence_de_resultat_est_explicite(corpus):
    result = search_jobs(query="cobol")
    assert result["total"] == 0
    assert "elargis" in result["note"].lower()


# -- fiche complete ----------------------------------------------------


def test_get_job_rend_le_texte_integral(corpus):
    job_id = search_jobs(query="python")["jobs"][0]["id"]
    complete = get_job(job_id)
    assert len(complete["description"]) > SNIPPET
    assert complete["skills"] == ["python", "django", "kubernetes"]


def test_identifiant_inconnu_explique(corpus):
    assert "error" in get_job("inexistant")


# -- facettes et agregats ----------------------------------------------


def test_facettes(corpus):
    valeurs = {v["value"] for v in list_facets("region")["values"]}
    assert valeurs == {"GE", "ZH", "69"}


def test_facette_invalide_expliquee(corpus):
    result = list_facets("colonne_inventee")
    assert "error" in result and "Disponibles" in result["error"]


def test_top_competences(corpus):
    terms = top_skills()["terms"]
    assert {t["value"] for t in terms} >= {"python", "soins_infirmiers", "agile"}


def test_top_competences_filtrable(corpus):
    terms = top_skills(region="ZH")["terms"]
    assert {t["value"] for t in terms} == {"soins_infirmiers", "geriatrie"}


def test_timeline(corpus):
    series = timeline(days=10)["series"]
    assert len(series) == 3
    assert series[0]["day"] <= series[-1]["day"]      # ordre chronologique


def test_stats(corpus):
    data = stats()
    assert data["total"] == 3
    assert data["sources"] == 2


def test_base_vide_dit_quoi_faire(base_vide):
    """Un corpus vide doit expliquer comment le remplir, pas rendre zero en silence."""
    data = stats()
    assert data["total"] == 0
    assert "crawl" in data["note"]


def test_sources_listees(corpus):
    sources = list_sources()["sources"]
    assert isinstance(sources, list)
    for entry in sources:
        assert {"name", "access", "notes", "jobs_collected"} <= set(entry)
