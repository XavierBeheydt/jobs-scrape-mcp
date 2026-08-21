"""Enregistrement des outils et des ressources aupres du serveur MCP."""

import json

import pytest

from jobs_scrape_mcp import mcp
from jobs_scrape_mcp.server import sources_resource, summary_resource

ATTENDUS = {
    "search_jobs", "get_job", "list_facets",
    "top_skills", "timeline", "stats", "list_sources",
}


@pytest.mark.asyncio
async def test_tous_les_outils_sont_exposes():
    noms = {tool.name for tool in await mcp.list_tools()}
    assert ATTENDUS <= noms


@pytest.mark.asyncio
async def test_chaque_outil_decrit_quand_l_appeler():
    """Une description qui dit seulement ce que fait l'outil ne suffit pas.

    Le modele choisit ses outils sur leur description : elle doit enoncer le
    declencheur, pas seulement la fonction.
    """
    for tool in await mcp.list_tools():
        assert tool.description, f"{tool.name} sans description"
        assert len(tool.description) > 120, f"{tool.name} : description trop maigre"


@pytest.mark.asyncio
async def test_ressources_exposees():
    uris = {str(r.uri) for r in await mcp.list_resources()}
    assert {"jobs://summary", "jobs://sources"} <= uris


def test_ressources_rendent_du_json_valide(corpus):
    json.loads(summary_resource())
    json.loads(sources_resource())


def test_le_serveur_porte_des_instructions():
    assert mcp.instructions
    assert "get_job" in mcp.instructions
