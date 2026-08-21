"""Serveur MCP donnant a une IA l'acces au corpus d'offres collecte.

Le corpus vit dans une base SQLite avec un index plein-texte FTS5. Ce module
n'y ajoute aucune logique de recherche : il expose la couche
``jobs_scrape.search`` du coeur sous forme d'outils MCP. La recherche reste
definie a un seul endroit, et l'interface web comme le serveur MCP en heritent.

**Le volume des reponses est le vrai enjeu de conception.** Un outil MCP renvoie
son resultat dans le contexte du modele. Rendre vingt annonces completes -- soit
plusieurs dizaines de milliers de signes -- saturerait ce contexte pour un
benefice nul : on ne lit pas vingt descriptions integrales pour repondre a
« quelles competences sont demandees a Geneve ». Les outils de liste rendent
donc des extraits, et ``get_job`` rend le texte complet d'**une** annonce.
"""

from __future__ import annotations

import json
import os
import sqlite3
from typing import Any

from jobs_scrape import search, storage
from mcp.server import MCPServer

__version__ = "0.1.0"

# Longueur d'extrait dans les resultats de liste. Assez pour juger de la
# pertinence d'une annonce, trop peu pour saturer le contexte du modele.
SNIPPET = 320

mcp = MCPServer(
    name="jobs-scrape",
    version=__version__,
    instructions=(
        "Corpus d'offres d'emploi suisses et francaises collectees par jobs-scrape. "
        "Utilise search_jobs pour toute question portant sur des postes, des "
        "competences demandees ou un marche local. Les resultats de liste sont "
        "tronques : appelle get_job pour lire une annonce en entier."
    ),
)


def _db_path() -> str:
    return os.environ.get("JOBS_SCRAPE_DB", os.path.join(
        os.environ.get("JOBS_SCRAPE_DATA_DIR", "data"), "jobs.db"))


def _connect() -> sqlite3.Connection:
    return storage.connect(_db_path())


def _summarize(row: dict[str, Any]) -> dict[str, Any]:
    """Extrait compact d'une offre, pour les resultats de liste."""
    description = row.get("description") or ""
    return {
        "id": row["fingerprint"],
        "title": row.get("title"),
        "company": row.get("company"),
        "location": " / ".join(x for x in (row.get("city"), row.get("region")) if x) or None,
        "country": row.get("country"),
        "contract_type": row.get("contract_type"),
        "workload": _workload(row),
        "salary": _salary(row),
        "remote_policy": row.get("remote_policy"),
        "seniority": row.get("seniority"),
        "skills": (row.get("skills") or [])[:10],
        "posted_at": row.get("posted_at"),
        "source": row.get("source"),
        "url": row.get("url"),
        "excerpt": (description[:SNIPPET] + "…") if len(description) > SNIPPET else description,
    }


def _workload(row: dict[str, Any]) -> str | None:
    low, high = row.get("workload_min"), row.get("workload_max")
    if low is None and high is None:
        return None
    if low == high:
        return f"{low}%"
    return f"{low}-{high}%"


def _salary(row: dict[str, Any]) -> str | None:
    low, high, currency = row.get("salary_min"), row.get("salary_max"), row.get("salary_currency")
    if low is None and high is None:
        return None
    if low == high:
        return f"{low:,.0f} {currency or ''}".strip()
    return f"{low:,.0f}-{high:,.0f} {currency or ''}".strip()


# --------------------------------------------------------------------- outils


@mcp.tool()
def search_jobs(
    query: str | None = None,
    region: str | None = None,
    city: str | None = None,
    company: str | None = None,
    skills: list[str] | None = None,
    source: str | None = None,
    contract_type: str | None = None,
    remote_policy: str | None = None,
    workload_min: int | None = None,
    salary_min: float | None = None,
    posted_since: str | None = None,
    limit: int = 15,
) -> dict[str, Any]:
    """Cherche des offres d'emploi dans le corpus collecte.

    Appelle cet outil des qu'une question porte sur des postes disponibles, des
    competences demandees sur un marche, des salaires observes ou l'activite de
    recrutement d'une entreprise. N'y reponds pas de memoire : le corpus contient
    des annonces reelles et datees.

    La recherche plein-texte porte sur l'intitule, l'entreprise, la ville, la
    description et les competences, et ignore les accents -- « developpeur »
    trouve « developpeur ». Sans ``query``, renvoie les offres les plus recentes
    correspondant aux filtres, ce qui permet aussi de parcourir.

    Args:
        query: termes de recherche libres. Un ``*`` final vaut prefixe.
        region: canton suisse (``GE``, ``VD``, ``ZH``) ou departement francais (``75``).
        city: ville, appariement partiel.
        company: entreprise, appariement partiel.
        skills: identifiants de competences, cumulatifs (toutes exigees).
        source: restreindre a un collecteur (``jobroom``, ``apec``, ``jobup``…).
        contract_type: ``permanent``, ``fixed_term``, ``temporary``, ``internship``…
        remote_policy: ``sur_site``, ``hybride``, ``distanciel``.
        workload_min: taux d'activite minimal en pourcent (marche suisse).
        salary_min: salaire minimal annonce.
        posted_since: date ISO ``AAAA-MM-JJ``.
        limit: nombre de resultats, 50 au maximum.

    Returns:
        ``total`` (nombre de correspondances), ``returned``, et ``jobs`` :
        des extraits. Utilise ``get_job`` avec un ``id`` pour le texte complet.
    """
    conn = _connect()
    try:
        filters = {k: v for k, v in {
            "region": region, "city": city, "company": company, "skills": skills,
            "source": source, "contract_type": contract_type,
            "remote_policy": remote_policy, "workload_min": workload_min,
            "salary_min": salary_min, "posted_since": posted_since,
        }.items() if v not in (None, [], "")}

        capped = max(1, min(int(limit), 50))
        rows = search.search(conn, query, limit=capped, **filters)
        total = search.count(conn, query, **filters)

        return {
            "total": total,
            "returned": len(rows),
            "jobs": [_summarize(r) for r in rows],
            "note": (
                "Extraits tronques ; appelle get_job(id) pour une annonce complete."
                if rows else
                "Aucune correspondance. Elargis la recherche, ou verifie que la "
                "collecte a bien tourne avec stats()."
            ),
        }
    finally:
        conn.close()


@mcp.tool()
def get_job(job_id: str) -> dict[str, Any]:
    """Renvoie une offre complete, description integrale comprise.

    A appeler apres ``search_jobs``, avec l'``id`` d'un resultat, quand le
    detail compte : conditions exactes, missions, profil recherche.

    Args:
        job_id: identifiant renvoye par ``search_jobs`` (champ ``id``).
    """
    conn = _connect()
    try:
        row = search.get(conn, job_id)
        if row is None:
            return {"error": f"aucune offre avec l'identifiant {job_id!r}"}
        return row
    finally:
        conn.close()


@mcp.tool()
def list_facets(field: str, limit: int = 25) -> dict[str, Any]:
    """Valeurs distinctes d'un champ et leur effectif.

    Sert a decouvrir ce que contient le corpus avant de filtrer : quels cantons
    sont couverts, quelles entreprises recrutent le plus, quelles sources sont
    presentes.

    Args:
        field: ``source``, ``region``, ``city``, ``company``, ``country``,
            ``contract_type``, ``remote_policy``, ``lang`` ou ``seniority``.
        limit: nombre de valeurs, 100 au maximum.
    """
    conn = _connect()
    try:
        return {"field": field, "values": search.facets(conn, field,
                                                        limit=max(1, min(int(limit), 100)))}
    except ValueError as exc:
        return {"error": str(exc)}
    finally:
        conn.close()


@mcp.tool()
def top_skills(
    field: str = "skills",
    limit: int = 25,
    source: str | None = None,
    region: str | None = None,
) -> dict[str, Any]:
    """Competences ou mots-cles les plus demandes.

    C'est l'outil a utiliser pour une question de tendance : « quelles
    competences sont recherchees dans le canton de Vaud », « qu'exige-t-on le
    plus souvent dans la construction ».

    Args:
        field: ``skills`` (identifiants normalises), ``keywords`` (termes libres),
            ``languages`` ou ``occupations``.
        limit: nombre de termes, 100 au maximum.
        source: restreindre a un collecteur.
        region: restreindre a un canton ou departement.
    """
    conn = _connect()
    try:
        filters = {k: v for k, v in {"source": source, "region": region}.items() if v}
        return {"field": field, "terms": search.top_terms(
            conn, field, limit=max(1, min(int(limit), 100)), **filters)}
    except ValueError as exc:
        return {"error": str(exc)}
    finally:
        conn.close()


@mcp.tool()
def timeline(days: int = 30, source: str | None = None, region: str | None = None) -> dict[str, Any]:
    """Volume d'offres publiees par jour.

    Repond aux questions d'activite dans le temps : le recrutement ralentit-il,
    quel jour publie-t-on le plus.

    Args:
        days: profondeur en jours, 365 au maximum.
        source: restreindre a un collecteur.
        region: restreindre a un canton ou departement.
    """
    conn = _connect()
    try:
        filters = {k: v for k, v in {"source": source, "region": region}.items() if v}
        return {"days": days, "series": search.timeline(
            conn, days=max(1, min(int(days), 365)), **filters)}
    finally:
        conn.close()


@mcp.tool()
def stats() -> dict[str, Any]:
    """Vue d'ensemble du corpus : volumes, sources, periode, couverture.

    A appeler en premier pour savoir ce que la base contient reellement avant
    de tirer une conclusion -- un corpus de soixante annonces ne permet pas les
    memes affirmations qu'un corpus de soixante mille.
    """
    conn = _connect()
    try:
        data = search.summary(conn)
        if not data["total"]:
            return {
                "total": 0,
                "note": ("La base est vide. Une collecte doit tourner d'abord : "
                         "jobs-scrape crawl <source>"),
            }
        return data
    finally:
        conn.close()


@mcp.tool()
def list_sources() -> dict[str, Any]:
    """Collecteurs installes, leur mode d'acces et leurs reserves connues.

    Utile pour expliquer d'ou viennent les donnees, et pourquoi une source
    attendue peut manquer.
    """
    from jobs_scrape import registry

    conn = _connect()
    try:
        collected = {row["value"]: row["count"] for row in search.facets(conn, "source", limit=50)}
    finally:
        conn.close()

    return {
        "sources": [
            {
                "name": name,
                "access": meta.access,
                "country": meta.country,
                "description": meta.description,
                "enabled_by_default": meta.enabled_by_default,
                "notes": meta.notes,
                "missing_env": list(meta.missing_env()),
                "jobs_collected": collected.get(name, 0),
            }
            for name, meta in registry.sources().items()
        ]
    }


# ------------------------------------------------------------------ ressources


@mcp.resource("jobs://summary", mime_type="application/json")
def summary_resource() -> str:
    """Etat courant du corpus, en lecture directe."""
    conn = _connect()
    try:
        return json.dumps(search.summary(conn), ensure_ascii=False, indent=2, default=str)
    finally:
        conn.close()


@mcp.resource("jobs://sources", mime_type="application/json")
def sources_resource() -> str:
    """Collecteurs installes et leurs reserves."""
    return json.dumps(list_sources(), ensure_ascii=False, indent=2, default=str)


def main() -> None:
    """Point d'entree : sert le protocole MCP sur l'entree/sortie standard."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
