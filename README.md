# jobs-scrape-mcp

Serveur **MCP** (Model Context Protocol) exposant le corpus
[jobs-scrape](https://github.com/XavierBeheydt/jobs-scrape) a une IA.

Une fois branche, Claude peut interroger directement les offres collectees :
« quelles competences sont demandees dans le canton de Vaud ? », « combien
d'offres a temps partiel dans la sante en aout ? », « resume-moi cette annonce ».

## Installation

```bash
uv pip install git+https://github.com/XavierBeheydt/jobs-scrape-mcp.git
claude mcp add jobs-scrape -- uv run jobs-scrape-mcp
```

Le serveur lit la meme base que la CLI :

| Variable | Defaut |
|---|---|
| `JOBS_SCRAPE_DB` | `data/jobs.db` |
| `JOBS_SCRAPE_DATA_DIR` | `data` |

## Outils exposes

| Outil | Quand l'appeler |
|---|---|
| `search_jobs` | Toute question sur des postes, competences demandees, salaires observes, activite d'une entreprise |
| `get_job` | Lire **une** annonce en entier, apres l'avoir trouvee |
| `list_facets` | Decouvrir ce que contient le corpus avant de filtrer (cantons, entreprises, sources) |
| `top_skills` | Question de tendance : ce qui est le plus demande, par region ou par source |
| `timeline` | Volume d'offres publiees par jour |
| `stats` | Vue d'ensemble — **a appeler en premier** pour savoir ce que la base contient |
| `list_sources` | D'ou viennent les donnees, et pourquoi une source attendue peut manquer |

Ressources : `jobs://summary` et `jobs://sources`.

## Le volume des reponses est le vrai enjeu

Un outil MCP renvoie son resultat **dans le contexte du modele**. Rendre vingt
annonces completes -- plusieurs dizaines de milliers de signes -- saturerait ce
contexte pour un benefice nul : on ne lit pas vingt descriptions integrales pour
repondre a « quelles competences sont demandees a Geneve ».

Ce serveur applique donc une regle simple :

- les outils de **liste** rendent des extraits (320 signes) et les champs
  structures qui servent a juger la pertinence ;
- `get_job` rend le texte complet, d'**une seule** annonce ;
- `limit` est borne a 50, quelle que soit la valeur demandee ;
- chaque reponse distingue `total` (correspondances) de `returned` (rendus),
  pour que le modele sache qu'il ne voit qu'une partie.

## Aucune logique de recherche ici

Le classement BM25, les facettes et les agregations vivent dans
`jobs_scrape.search`, au coeur du projet. Ce module se contente de les exposer.
La recherche reste definie **a un seul endroit** — l'interface web et le serveur
MCP en heritent, et une amelioration du classement profite aux deux.

## Descriptions d'outils : le declencheur, pas seulement la fonction

Le modele choisit ses outils sur leur description. Une description qui dit
seulement *ce que fait* un outil laisse le modele deviner *quand* l'utiliser.
Chaque outil enonce donc son declencheur — « appelle cet outil des qu'une
question porte sur des postes disponibles » — et un test verifie qu'aucune
description ne reste maigre.

## Developpement

```bash
uv venv
uv pip install git+https://github.com/XavierBeheydt/jobs-scrape.git
uv pip install -e ".[dev]"
uv run pytest -q      # hors ligne, base temporaire
```
