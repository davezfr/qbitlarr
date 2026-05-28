# qBitlarr

**Langue :** [English](README.md) | [中文](README.zh-CN.md) | Français

**Une passerelle légère entre Prowlarr et qBittorrent, avec support REST, MCP et CLI.**

qBitlarr s'adresse aux personnes qui utilisent déjà Plex, Jellyfin ou Emby et qui veulent permettre à des amis, à la famille ou à un agent LLM de demander des films et des séries sans leur donner accès à qBittorrent et sans installer toute la pile Sonarr + Radarr.

qBitlarr est un petit service FastAPI qui peut :

- Recevoir une demande en langage naturel, un identifiant IMDb ou une URL IMDb.
- Chercher dans vos indexeurs Prowlarr.
- Choisir la meilleure release selon des préférences de qualité configurables.
- Ajouter le téléchargement à votre qBittorrent existant.
- Exposer la même logique via REST, MCP et une petite CLI, afin de s'intégrer à Claude Desktop, Cursor, ChatGPT custom tools, des bots Telegram, des scripts shell, des cron jobs ou vos propres agents.

Fonctionne avec n'importe quel client HTTP, Claude/Cursor/ChatGPT via MCP, ou la CLI `qbitlarr`.

## Architecture

![qBitlarr architecture: a friend, family member, shell script, or LLM agent talks REST, MCP, or CLI to the qbitlarr FastAPI service, which uses Prowlarr and FlareSolverr to search torrent indexers and then drives your own qBittorrent Web UI, which saves files into your Plex/Jellyfin/Emby library.](docs/architecture.png)

Source modifiable du diagramme REST / MCP / CLI : [docs/architecture.svg](docs/architecture.svg).

## Ce que Docker Compose lance

- `qbitlarr` — le service FastAPI sur `http://localhost:8000`
- `prowlarr` — Prowlarr inclus sur `http://localhost:9696`
- `flaresolverr` — FlareSolverr inclus sur `http://localhost:8191`

qBittorrent **n'est pas** inclus. Pointez qBitlarr vers un qBittorrent existant — application de bureau, NAS, seedbox, conteneur séparé — avec `QBIT_URL`, `QBIT_USERNAME` et `QBIT_PASSWORD`.

## Configuration de qBittorrent

qBitlarr a besoin d'une installation qBittorrent existante, parce que chaque personne organise ses téléchargements et ses chemins de médiathèque différemment : application de bureau, NAS, seedbox ou conteneur séparé. qBitlarr parle uniquement à qBittorrent via son API Web UI.

Avant de lancer qBitlarr :

1. Installez qBittorrent là où vos téléchargements doivent s'exécuter.
2. Dans qBittorrent, ouvrez **Preferences / Options → Web UI** et activez la Web User Interface.
3. Définissez ou vérifiez le nom d'utilisateur et le mot de passe de la Web UI.
4. Renseignez ces valeurs dans `.env` :

```sh
QBIT_URL=http://host.docker.internal:8080
QBIT_USERNAME=your-webui-username
QBIT_PASSWORD=your-webui-password
```

Utilisez `http://host.docker.internal:8080` quand qBittorrent tourne sur la même machine que Docker Compose. Si qBittorrent tourne sur un NAS, une seedbox ou un autre ordinateur, utilisez plutôt l'URL LAN de cette machine, par exemple `http://192.168.1.50:8080`. N'utilisez pas `localhost` dans `.env` pour un qBittorrent installé sur l'hôte ; depuis Docker, `localhost` désigne le conteneur qBitlarr lui-même.

## Démarrage rapide

```sh
cp .env.example .env
# éditez .env : renseignez QBIT_URL, QBIT_USERNAME et QBIT_PASSWORD depuis votre qBittorrent Web UI

# 1. Lancez d'abord Prowlarr pour récupérer sa clé API
docker compose up -d prowlarr flaresolverr

# 2. Ouvrez http://localhost:9696, terminez la configuration initiale, ajoutez des indexeurs,
#    puis copiez la clé API depuis Settings -> General -> Security
# 3. Placez la clé dans .env avec PROWLARR_API_KEY

# 4. Lancez le reste
docker compose up -d --build

# 5. Testez
curl -X POST http://localhost:8000/handle \
  -H 'Content-Type: application/json' \
  -d '{"user_message":"tt0045877"}'
```

Pour vérifier aussi que Prowlarr et qBittorrent sont joignables :

```sh
curl 'http://localhost:8000/health?deep=true'
```

## À quoi ça ressemble

Une fois qBitlarr branché à votre agent (ou via la CLI), vous lui parlez comme à un ami qui connaît votre configuration média :

Les exemples ci-dessous utilisent [The Hitch-Hiker (1953)](https://www.imdb.com/title/tt0045877/), un film du domaine public listé par la Library of Congress dans son ensemble [Public Domain Films from the National Film Registry](https://www.loc.gov/free-to-use/public-domain-films-from-the-national-film-registry/). Les droits peuvent quand même varier selon la juridiction et selon la restauration, la bande-son, les sous-titres ou l'édition précise.

<table>
  <tr>
    <td width="50%">
      <img src="docs/screenshots/telegram-imdb-share.jpg" alt="Exemple Telegram : partager la page IMDb de The Hitch-Hiker avec un agent, qui lance le téléchargement via qBitlarr.">
      <br>
      <em>Capture d'écran fournie à titre d'exemple uniquement. Le titre de base affiché est un exemple du domaine public (Public Domain) ; les droits peuvent varier selon la juridiction, la restauration, la bande-son, les sous-titres ou l'édition précise.</em>
    </td>
    <td width="50%">
      <img src="docs/screenshots/telegram-public-domain-selection.jpg" alt="Exemple Telegram : choisir et vérifier l'état d'un téléchargement de Night of the Living Dead 1968.">
      <br>
      <em>Capture d'écran fournie à titre d'exemple uniquement. Le titre de base affiché est un exemple du domaine public (Public Domain) ; les droits peuvent varier selon la juridiction, la restauration, la bande-son, les sous-titres ou l'édition précise.</em>
    </td>
  </tr>
</table>

> **Vous :** *Télécharge The Hitch-Hiker.*
> **Agent :** Téléchargement automatique lancé : The Hitch-Hiker en 1080p WEB-DL H.264.

> **Vous :** *Télécharge tt0045877 depuis IMDb.*
> **Agent :** Téléchargement automatique lancé : The Hitch-Hiker en 1080p WEB-DL H.264.

> **Vous :** *Je veux The Hitch-Hiker en 4K.*
> **Agent :** Téléchargement automatique lancé : The Hitch-Hiker en 2160p UHD BluRay REMUX H.265.

> **Vous :** *Qu'est-ce qui télécharge en ce moment ?*
> **Agent :** The Hitch-Hiker — 42 % — téléchargement à 8,4 Mo/s · fin estimée dans 6 minutes

> **Vous :** *Trouve-moi The Hitch-Hiker, mais je veux choisir la release.*
> **Agent :** Voici les meilleurs résultats, répondez avec le numéro :
>   1. The.Hitch-Hiker.1953.1080p.WEB-DL.H.264 — 152 seeders
>   2. The.Hitch-Hiker.1953.720p.BluRay.H.264 — 84 seeders
>   3. The.Hitch-Hiker.1953.DVDRip.H.264 — 60 seeders

En coulisses : quand l'agent reçoit un titre clair, il choisit automatiquement la meilleure release 1080p ayant assez de seeders et la met en file dans votre qBittorrent. Quand le titre est ambigu (recherche libre), il renvoie une liste triée et attend votre choix. Les réponses de statut viennent de `qbitlarr_list_downloads`, qui remonte en direct l'état de qBittorrent — progression, vitesse, ETA, seeders. Vous pouvez toujours dire *"4K"*, *"Remux"* ou *"720p HEVC"* pour forcer une qualité différente.

### Astuce : partager directement depuis l'app IMDb

Le moyen le plus rapide d'utiliser qBitlarr, c'est de ne rien taper du tout :

1. Dans l'app IMDb (ou n'importe quel site qui affiche une URL IMDb), trouvez ce que vous voulez.
2. Appuyez sur l'icône de partage → choisissez l'app où vit votre agent (Telegram, WhatsApp, Discord, Signal, iMessage, etc.).
3. L'agent reçoit une URL du type `https://www.imdb.com/title/tt0045877/` et identifie le titre tout seul — pas de saisie, pas de fautes d'orthographe, pas d'ambiguïté.

Un identifiant IMDb brut comme `tt0045877` marche pareil si vous en avez un sous la main. qBitlarr extrait l'ID, fait une requête précise auprès de vos indexeurs, et met le meilleur résultat en file en quelques secondes.

## Quand l'utiliser plutôt que Sonarr / Radarr

Utilisez **Sonarr/Radarr** si vous voulez un gestionnaire de médiathèque complet : suivi des épisodes, politiques de mise à niveau, surveillance automatique des nouvelles sorties, profils de qualité très détaillés.

Utilisez **qBitlarr** si vous voulez simplement : *"un ami donne le nom d'un film → il apparaît dans Plex une heure plus tard."* Pas de médiathèque, pas de surveillance, pas d'interface de profils. Un service, quelques variables d'environnement, et c'est tout.

## Utilisation responsable

qBitlarr est une passerelle d'automatisation. Il ne fournit pas de contenu, d'indexeurs, de trackers ni de conseil juridique. Utilisez-le uniquement avec des indexeurs et des médias auxquels vous avez le droit d'accéder dans votre juridiction.

## Configurer les indexeurs dans Prowlarr

Si vous découvrez **Prowlarr** : c'est un *agrégateur d'indexeurs*. Il se connecte à plusieurs sites de torrents, appelés indexeurs, et donne à qBitlarr une seule API de recherche. Sans lui, qBitlarr devrait connaître les détails de dizaines de sites différents. Vous ajoutez les indexeurs une fois dans Prowlarr, puis chaque recherche qBitlarr les interroge en parallèle.

**Ajouter un indexeur :**

1. Ouvrez `http://localhost:9696` puis allez dans **Indexers → + Add Indexer**.
2. Tapez le nom de l'indexeur dans le filtre.
3. **Indexeur public** : en général, cliquez simplement sur **Save**. Aucun compte n'est nécessaire.
4. **Tracker privé** : collez le cookie, la clé API ou le passkey de votre compte sur ce tracker. Les champs varient selon les trackers, et le formulaire Prowlarr indique ce qui est requis.
5. Cliquez sur **Test** pour vérifier que Prowlarr peut l'atteindre, puis sur **Save**.
6. L'indexeur possède maintenant un ID numérique, visible avec `curl http://localhost:8000/prowlarr/indexers`.

Pour les indexeurs derrière Cloudflare, ajoutez aussi le proxy tag `flaresolverr`. Voir [Pourquoi FlareSolverr est inclus](#pourquoi-flaresolverr-est-inclus).

**Indexeurs publics vs trackers privés :**

- **Indexeurs publics** : souvent rapides à ajouter, mais les résultats sont plus bruités : plus de torrents morts, de spam et de fausses releases.
- **Trackers privés** : nécessitent un compte et ont souvent des règles d'accès plus strictes. Les champs de configuration varient ; suivez les exigences des trackers que vous êtes autorisé à utiliser.

**Recommandations :**

- **Commencez avec 2 à 4 indexeurs, pas 20.** Chaque indexeur ajoute de la latence à chaque recherche. Un site lent peut ralentir toute la requête, et empiler des indexeurs publics empile souvent du bruit plutôt que de la qualité.
- **Mélangez couverture et qualité.** Un ou deux indexeurs publics généralistes comme filet de sécurité, plus les trackers privés auxquels vous avez accès, donnent une bonne base.
- **Ignorez `Sync Profiles`** sauf si vous utilisez aussi Sonarr ou Radarr. qBitlarr n'en a pas besoin.

Une fois les indexeurs configurés, vous pouvez définir des IDs primary et fallback dans [Sélection des indexeurs](#sélection-des-indexeurs). qBitlarr cherchera d'abord dans vos indexeurs rapides et fiables, puis ne basculera vers les sources plus larges ou plus lentes que si nécessaire.

## Pourquoi FlareSolverr est inclus

Certains indexeurs populaires sont protégés par le **challenge anti-bot de Cloudflare**. Une requête HTTP simple — celle que Prowlarr envoie par défaut — reçoit une page de challenge HTML au lieu de résultats de recherche. L'indexeur semble alors ne rien renvoyer.

**FlareSolverr** est un petit proxy basé sur Chrome headless qui résout ces challenges pour Prowlarr. Quand Prowlarr est configuré pour faire passer certains indexeurs par lui, FlareSolverr ouvre la page dans un vrai navigateur, attend que Cloudflare valide la session, puis renvoie les cookies à Prowlarr pour que la recherche fonctionne.

qBitlarr l'inclut parce qu'un utilisateur qui ajoute un indexeur protégé par Cloudflare dans Prowlarr rencontre vite ce blocage, et la solution officielle revient souvent à installer FlareSolverr séparément. Le fournir dans le compose évite cette friction.

**Le connecter dans Prowlarr** une fois le premier démarrage terminé :

1. Ouvrez Prowlarr sur `http://localhost:9696`.
2. Allez dans **Settings → Indexers → Indexer Proxies**.
3. Cliquez sur **+** puis choisissez **FlareSolverr**.
4. Définissez **Host** à `http://flaresolverr:8191`, le hostname interne du compose, et donnez-lui un **Tag** comme `flaresolverr`.
5. Sauvegardez. Ensuite, pour chaque indexeur protégé par Cloudflare, ouvrez sa configuration, ajoutez ce même tag `flaresolverr`, puis sauvegardez.

Les indexeurs sans ce tag ne passent pas par FlareSolverr, donc il n'y a pas de coût pour les sites non protégés. Si vous n'utilisez aucun indexeur protégé par Cloudflare, vous pouvez arrêter le conteneur avec `docker compose stop flaresolverr` et qBitlarr continuera à fonctionner.

## Préférences de qualité

Par défaut, qBitlarr vise **1080p WEB-DL H.264** avec au moins 5 seeders. Vous pouvez changer les valeurs par défaut avec :

```sh
QBITLARR_PREFER_RESOLUTION=1080p   # 480p | 720p | 1080p | 2160p
QBITLARR_PREFER_SOURCE=WEB-DL      # WEB-DL | WEBRip | BluRay | HDTV
QBITLARR_PREFER_CODEC=H.264        # H.264 | H.265
QBITLARR_MIN_SEEDERS=5
```

Les utilisateurs peuvent aussi remplacer ces préférences dans chaque demande en langage naturel :

- `"The Hitch-Hiker 4K"` → force 2160p
- `"The Hitch-Hiker Remux"` → force une release Remux
- `"The Hitch-Hiker 720p HEVC"` → 720p H.265

## Modes de sortie

`POST /handle` accepte un champ optionnel `mode` qui contrôle le comportement lorsqu'un IMDb ID est donné :

- `auto` *(par défaut)* — choisit la meilleure release et l'ajoute à la file. Idéal pour un usage simple par des amis ou la famille.
- `manual` — renvoie toujours une liste classée et n'ajoute rien à la file. Idéal pour les utilisateurs qui veulent choisir.
- `confirm` — renvoie le meilleur choix et quelques alternatives, mais n'ajoute rien à la file. Idéal pour les flux agentiques qui demandent une confirmation humaine avant d'agir.

Changez le mode serveur par défaut avec `QBITLARR_DEFAULT_MODE=auto|manual|confirm`. Les réponses d'auto-download incluent toujours une liste `alternatives` avec 2 à 3 options, ce qui permet à un agent de proposer "ou vouliez-vous plutôt..." sans second appel d'outil.

## Connecter un agent

qBitlarr est livré comme un **serveur MCP**, donc n'importe quel agent qui parle le [Model Context Protocol](https://modelcontextprotocol.io) — Claude Desktop, Cursor, Cline, Hermes, OpenClaw, ChatGPT via un bridge MCP, votre propre agent maison — peut l'utiliser.

Les outils MCP sont neutres côté langue. Vous pouvez poser la question en anglais, chinois, français ou toute autre langue que le LLM de votre agent sait gérer ; l'agent peut répondre dans la même langue. Ce comportement multilingue dépend du LLM derrière votre agent, pas de qBitlarr lui-même.

Deux transports sont disponibles :

- **stdio MCP** — ce que la plupart des applications agent de bureau préfèrent. Elles lancent `bin/qbitlarr-mcp` comme sous-processus.
- **HTTP MCP** — exposé sur `http://localhost:8000/mcp` pour les hosts qui préfèrent HTTP.

Outils exposés par les deux transports : `qbitlarr_handle`, `qbitlarr_search`, `qbitlarr_download`, `qbitlarr_list_downloads`, `qbitlarr_get_query_snapshot`, `qbitlarr_list_prowlarr_indexers`, `qbitlarr_health`.

Si `QBITLARR_API_KEY` est défini, les deux transports exigent un header `X-API-Key`. Le MCP stdio lit la même variable d'environnement.

### Claude Desktop

Éditez `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) ou `%APPDATA%\Claude\claude_desktop_config.json` (Windows) :

```json
{
  "mcpServers": {
    "qbitlarr": {
      "command": "/absolute/path/to/qbitlarr/bin/qbitlarr-mcp",
      "env": {
        "QBITLARR_API_URL": "http://localhost:8000",
        "QBITLARR_API_KEY": ""
      }
    }
  }
}
```

Redémarrez Claude Desktop. Les outils qbitlarr apparaissent dans la liste et Claude les utilise quand vous parlez de films ou de séries.

### Cursor

Settings → **MCP** → **Add new MCP server** :

```json
{
  "mcpServers": {
    "qbitlarr": {
      "command": "/absolute/path/to/qbitlarr/bin/qbitlarr-mcp"
    }
  }
}
```

### N'importe quel autre host MCP (Hermes, OpenClaw, Cline, agents personnalisés)

Le schéma est identique — tous supportent l'un ou l'autre, voire les deux transports :

- **Voie stdio** : configurez le host pour lancer `bin/qbitlarr-mcp` comme sous-processus (avec les variables d'environnement pour l'URL de l'API et la clé optionnelle).
- **Voie HTTP** : pointez le host vers `http://localhost:8000/mcp`, en ajoutant le header `X-API-Key` si vous en avez défini un.

### Indiquer à l'agent quand utiliser qBitlarr

Si votre agent expose un system prompt ou un champ "tool instructions", ajoutez une courte indication pour qu'il pense à qBitlarr au bon moment :

> *Quand l'utilisateur demande à télécharger un film, une série ou un anime auquel il est autorisé à accéder, utilise les outils MCP qbitlarr. Par défaut, appelle `qbitlarr_handle` — il accepte les IDs IMDb, les URLs IMDb et le texte libre, et décide tout seul s'il faut auto-choisir ou renvoyer une liste. Ne reviens à `qbitlarr_search` + `qbitlarr_download` que quand l'utilisateur veut explicitement choisir dans une liste.*

Cela aide les agents qui ne savaient pas que vous aviez un downloader connecté.

### Vérification rapide

Une fois branché, demandez à l'agent : *"Utilise qbitlarr_health pour vérifier que le service tourne."* S'il renvoie `{"status": "ok"}`, c'est connecté. Ajoutez `--deep` (ou passez `deep: true`) pour vérifier aussi que Prowlarr et qBittorrent répondent.

## CLI

La CLI est un client léger pour la même API REST que celle utilisée par MCP. Elle lit `QBITLARR_API_URL`, `QBITLARR_API_KEY` et `QBITLARR_API_TIMEOUT_SECONDS` depuis l'environnement, avec des flags disponibles pour les surcharger.

`handle` affiche par défaut une réponse lisible par un humain. Ajoutez `--json` pour obtenir la réponse structurée brute. Les autres sous-commandes affichent du JSON par défaut pour être utilisées avec `jq`.

```sh
bin/qbitlarr handle "tt0045877"
bin/qbitlarr handle "The Hitch-Hiker" --mode manual
bin/qbitlarr handle "The Hitch-Hiker" --mode manual --json
bin/qbitlarr search --query "The Hitch-Hiker 1953 1080p" | jq '.[0]'
bin/qbitlarr download 'magnet:?xt=urn:btih:...'
bin/qbitlarr downloads --watch
bin/qbitlarr health --deep
bin/qbitlarr indexers
```

Mettez les liens magnet entre guillemets dans votre shell, car ils contiennent souvent `&`.

Dans le conteneur Docker, lancez le même module CLI avec `docker compose exec qbitlarr python -m app.cli health --deep`. Le launcher `bin/qbitlarr` est destiné à l'utilisation depuis le checkout sur l'hôte.

## Authentification

Pour un déploiement au-delà de localhost, définissez `QBITLARR_API_KEY`. Chaque requête REST et MCP devra alors fournir le header `X-API-Key` :

```sh
curl -H 'X-API-Key: change-this' http://localhost:8000/health
```

Laissez vide pour un usage local sans authentification.

## URLs Prowlarr

`PROWLARR_URL` est l'URL utilisée par qBitlarr pour appeler l'API Prowlarr. Dans Docker Compose, elle vaut par défaut `http://prowlarr:9696`, le hostname interne du service. La plupart des utilisateurs n'ont pas besoin de la modifier.

`PROWLARR_DOWNLOAD_URL` est optionnel. Définissez-le seulement lorsque Prowlarr renvoie des URLs de téléchargement proxy que qBitlarr doit réécrire avant de récupérer le fichier `.torrent`, par exemple si qBitlarr doit joindre Prowlarr via une adresse LAN plutôt que par le hostname Docker interne.

## Sélection des indexeurs

`PROWLARR_PRIMARY_INDEXER_IDS` et `PROWLARR_FALLBACK_INDEXER_IDS` sont des listes optionnelles d'IDs d'indexeurs séparés par des virgules.

- Laissez les deux vides pour laisser Prowlarr chercher dans tous les indexeurs applicables.
- Définissez des IDs primary pour privilégier un sous-ensemble fiable.
- Définissez des IDs fallback pour essayer des indexeurs plus larges ou plus lents seulement lorsque les résultats primary sont absents ou inadaptés.

Découvrez les IDs une fois Prowlarr configuré :

```sh
curl http://localhost:8000/prowlarr/indexers
```

## Chemins de sauvegarde

Les auto-downloads de `/handle` choisissent un chemin selon le type de média et la résolution :

- `QBITLARR_SAVE_PATH_MOVIE=/downloads/movies`
- `QBITLARR_SAVE_PATH_MOVIE_4K=/downloads/movies-4k`
- `QBITLARR_SAVE_PATH_TV=/downloads/tv`

`/handle` et `/download` acceptent aussi un champ optionnel `save_path` pour les remplacements ponctuels. Ces chemins doivent se trouver sous l'une des racines configurées ci-dessus, ou sous une entrée de `QBITLARR_EXTRA_SAVE_PATHS` séparée par des virgules, par exemple `/media/Kids`.

## API REST

| Method | Path | Objectif |
| --- | --- | --- |
| GET | `/health` | Vérification de vie du service |
| GET | `/health?deep=true` | Vie du service + accessibilité Prowlarr/qBittorrent |
| POST | `/handle` | Point d'entrée principal : chercher et éventuellement ajouter à la file |
| POST | `/search` | Recherche Prowlarr brute |
| POST | `/download` | Ajouter un lien de téléchargement connu |
| GET | `/downloads` | Lister les torrents dans qBittorrent |
| GET | `/queries/{query_id}` | Relire un snapshot de recherche sauvegardé |
| GET | `/prowlarr/indexers` | Lister les indexeurs Prowlarr avec leurs IDs |

Exemple : ajouter un lien connu dans un dossier précis.

```sh
curl -X POST http://localhost:8000/download \
  -H 'Content-Type: application/json' \
  -d '{"download_link":"magnet:?xt=urn:btih:...","save_path":"/media/Kids"}'
```

## Structure du projet

```
qbitlarr/
├── app/                          Service FastAPI, l'implémentation canonique
│   ├── main.py                   Entrée de l'app, monte les routers et HTTP MCP sur /mcp
│   ├── config.py                 Réglages par variables d'environnement
│   ├── models.py                 Schémas Pydantic de requête/réponse
│   ├── exceptions.py
│   ├── client.py                 Client HTTP async partagé par CLI et MCP
│   ├── cli.py                    CLI argparse `qbitlarr`
│   ├── api/                      Handlers des endpoints REST
│   │   ├── handle.py             /handle, orchestration principale : recherche → classement → file
│   │   ├── search.py             /search, passthrough Prowlarr brut
│   │   ├── download.py           /download, ajout d'un lien connu
│   │   ├── downloads_list.py     /downloads, état qBittorrent
│   │   ├── query_snapshots.py    /queries/{id}, snapshots de recherche sauvegardés
│   │   └── prowlarr.py           /prowlarr/indexers, découverte d'indexeurs
│   ├── domain/                   Logique pure, sans I/O
│   │   ├── quality.py            Parsing de titres, scoring, QualityPreferences
│   │   ├── search_results.py     Normalisation des résultats Prowlarr
│   │   └── torrent_metadata.py   Décodage de fichiers .torrent pour vérification
│   └── services/                 Clients de services externes
│       ├── prowlarr.py
│       ├── qbittorrent.py
│       └── query_snapshots.py
├── mcp_server/
│   └── server.py                 Serveur MCP stdio, wrappers fins autour de app/client.py
├── bin/
│   ├── qbitlarr                  Launcher CLI
│   └── qbitlarr-mcp              Launcher du serveur MCP stdio
├── tests/                        Suite pytest
├── docs/
│   ├── architecture.png
│   ├── architecture.svg
│   └── screenshots/              Captures d'écran du README
├── docker-compose.yml            Inclut qbitlarr + prowlarr + flaresolverr
├── Dockerfile                    Construit l'image qbitlarr
├── requirements.txt
├── .env.example                  À copier vers .env puis remplir
├── README.md                     README anglais
├── README.zh-CN.md               README chinois simplifié
└── README.fr.md                  README français
```

**Où se trouvent les parties importantes :**

- **`app/api/handle.py`** contient la logique centrale : détection IMDb, cascade primary/fallback d'indexeurs, classement, modes (`auto`/`manual`/`confirm`).
- **`app/domain/quality.py`** est la couche pure de scoring/classement, sans appels réseau. Modifiez ce fichier si vous voulez changer la façon dont les releases sont choisies.
- **`app/client.py`** est le seul client HTTP. La CLI (`app/cli.py`) et le MCP stdio (`mcp_server/server.py`) l'utilisent tous les deux, ce qui garde un comportement cohérent entre les interfaces.
- **L'API REST est la surface canonique.** MCP et CLI sont tous les deux des clients de cette API. Si vous intégrez qBitlarr dans un autre système, appelez directement les endpoints REST.

## Projets tiers

qBitlarr s'intègre avec ces projets tiers :

- **[Prowlarr](https://github.com/Prowlarr/Prowlarr)** — GPL-3.0. qBitlarr peut lancer Prowlarr comme service Docker Compose séparé et communique avec lui via son API HTTP.
- **[qBittorrent](https://github.com/qbittorrent/qBittorrent)** — GPL-2.0. qBitlarr attend que vous fournissiez qBittorrent séparément et communique avec lui via son API Web UI.
- **[FlareSolverr](https://github.com/FlareSolverr/FlareSolverr)** — MIT. La configuration Docker Compose de qBitlarr l'inclut comme proxy de challenge optionnel pour les indexeurs Prowlarr qui en ont besoin.

qBitlarr n'est pas affilié à Prowlarr, qBittorrent, FlareSolverr ou leurs mainteneurs, et n'est ni approuvé ni sponsorisé par eux.

## License

MIT.
