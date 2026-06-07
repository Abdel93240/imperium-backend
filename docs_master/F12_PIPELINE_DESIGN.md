# F12 — Pipeline Design Claude

**Version :** 1.0
**Date :** 2026-06-04
**Statut :** DOCUMENTATION PIPELINE DESIGN — documentation only, aucun code modifié, aucun test lancé.
**Périmètre :** orchestrateur Claude Design, worktrees frontend, génération de `CLAUDE.md`, preview Vite, règles d'isolation.
**Sources vérifiées :** `/opt/orchestrator/claude_design_runner.py`, `/opt/orchestrator/tests/`, `docs_master/59_DESIGN_SYSTEM_V1_DRAFT.md`, `docs_master/64_FRONTEND_GENERATION_PLAN_V1.md`.

Ce document décrit le pipeline design utilisé pour produire des écrans frontend isolés sans toucher au backend Imperium. Il complète le plan de génération frontend V1 et garde la règle produit principale : les apps restent des interfaces, le backend et les workflows restent le cerveau.

---

## 1. Mission du document

Ce document verrouille quatre points opérationnels :

1. Le rôle du fichier `CLAUDE.md` généré par worktree.
2. Les règles de sécurité et d'isolation du pipeline design.
3. Les limites réelles du code au moment de la rédaction.
4. L'état des tests pytest qui couvrent ce pipeline.

Il ne définit pas un nouveau runtime Android, ne branche aucun endpoint backend et ne crée aucune règle métier frontend.

## 2. Pipeline officiel

Le pipeline design reste celui du document `64_FRONTEND_GENERATION_PLAN_V1.md` :

```text
Prompt
↓
Worktree
↓
Preview URL
↓
Validation humaine
↓
Correction éventuelle
↓
Merge
```

Dans le code actuel, le pipeline est porté par `/opt/orchestrator/claude_design_runner.py`.

Fonctions principales vérifiées :

```text
ensure_frontend_app_workspace(app_key)
prepare_design_worktree(session_id, app_key)
generate_design_claude_md(app_key, worktree_path, asset_list, font_list=None, texture_list=None)
run_claude_design_in_worktree(...)
start_design_preview(...)
preview_url_for(app_key, session_id, ...)
```

## 3. Worktree par session

Chaque session design crée un worktree frontend isolé :

```text
/opt/orchestrator/design_sessions/<session_id>/worktree/
```

La branche associée suit le format :

```text
design/<session_id>
```

Le repo applicatif de base est situé sous :

```text
/opt/frontend-apps/<app_key>/
```

Les `app_key` autorisés sont limités à :

```text
imperium
vault
vector
pulse
path
```

Le worktree est créé par `prepare_design_worktree(session_id, app_key)`. Cette fonction refuse les `app_key` inconnus, refuse les `session_id` contenant `/` ou `..`, refuse un worktree déjà présent, puis copie les assets, polices et textures avant de générer `CLAUDE.md`.

## 4. `CLAUDE.md` généré par worktree

La fonction exacte est :

```python
generate_design_claude_md(
    app_key: str,
    worktree_path: Path,
    asset_list: list[str],
    font_list: list[str] | None = None,
    texture_list: list[str] | None = None,
) -> Path
```

Elle écrit un fichier par session :

```text
<worktree_path>/CLAUDE.md
```

Objectif : placer le contexte design lourd dans un fichier local lu par Claude Code au démarrage de la session, au lieu de répéter la liste des assets, polices, textures et règles strictes dans chaque prompt. Cela économise des tokens et stabilise les consignes.

Le prompt système généré par `_build_design_system_prompt(...)` rappelle explicitement :

```text
Consulte CLAUDE.md dans le worktree: il liste les assets disponibles dans
/assets/ et les textures disponibles dans /textures/.
```

## 5. Contenu de `CLAUDE.md`

Le fichier généré contient les sections suivantes :

```text
# Claude Design - <app_key>

## Assets disponibles
## Polices disponibles
## Textures disponibles
## Titres dorés / textures
## Style de l'app <app_key>
## Règles STRICTES
```

Les assets sont formatés par `_format_assets_for_claude_md(asset_list)`.

Les polices sont découvertes ou reçues via `font_list`, puis formatées par `_format_fonts_for_claude_md(font_list)`. Pour chaque police supportée, le fichier inclut un exemple `@font-face` :

```css
@font-face {
  font-family: 'ImperiumDisplay';
  src: url('/fonts/ImperiumDisplay.woff2') format('woff2');
  font-display: swap;
}
```

Les textures sont découvertes ou reçues via `texture_list`, puis formatées par `_format_textures_for_claude_md(texture_list)`.

La technique des titres dorés est fournie par `_texture_css_examples(...)` :

```css
.titre-texture {
  font-family: 'ImperiumDisplay', serif;
  background-image: url('/textures/texture_or_titre.png');
  background-size: cover;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
```

Le style de l'app est lu par `_read_app_style_guidance(app_key)`. Si un fichier `STYLE.md`, `style.md`, `DIRECTION.md` ou `README.md` existe dans `/opt/orchestrator/reference_images/<app_key>/`, il est prioritaire. Sinon, le code utilise une direction locale par défaut.

## 6. Règles anti-placeholder

`CLAUDE.md` termine par des règles strictes :

```text
- Utilise TOUJOURS les assets fournis dans /assets/.
- N'invente JAMAIS de placeholder.
- N'utilise JAMAIS d'images externes ou de liens.
- Si un asset manque pour un besoin, signale-le plutôt que d'inventer.
```

Cette règle est volontairement plus stricte que les anciennes policies de placeholder documentaires du backend. Dans le pipeline design génératif, l'agent doit utiliser les assets réels copiés dans le worktree ou signaler le manque.

## 7. Assets, polices et textures

Les assets applicatifs sont copiés par :

```text
copy_app_assets_to_worktree(app_key, worktree_path)
```

Racine source :

```text
/opt/orchestrator/assets_registry/<app_key>/
```

Destination Vite :

```text
<worktree>/public/assets/
```

Les images de référence sont copiées sous :

```text
<worktree>/public/assets/reference/
```

Les polices sont copiées par :

```text
copy_app_fonts_to_worktree(app_key, worktree_path)
```

Racine source :

```text
/opt/orchestrator/fonts/<app_key>/
```

Destination Vite :

```text
<worktree>/public/fonts/
```

Extensions supportées :

```text
.ttf
.woff
.woff2
.otf
```

Les textures sont copiées par :

```text
copy_app_textures_to_worktree(app_key, worktree_path)
```

Racine source :

```text
/opt/orchestrator/textures/<app_key>/
```

Destination Vite :

```text
<worktree>/public/textures/
```

Extensions supportées :

```text
.png
.jpg
.jpeg
.webp
```

## 8. Sécurité et isolation

Le pipeline design est conçu pour éviter qu'une session frontend modifie le backend monorepo.

Règles effectives vérifiées dans le code :

| Règle | Implémentation |
|---|---|
| Worktree isolé par session | `prepare_design_worktree(...)` crée `/opt/orchestrator/design_sessions/<sid>/worktree/`. |
| App whitelistée | `DESIGN_APP_KEYS = ("imperium", "vault", "vector", "pulse", "path")`. |
| Path traversal refusé | `session_id` contenant `/` ou `..` déclenche `ValueError`. |
| Backend interdit | `_backend_path_refusal(...)` refuse les chemins sous `/opt/imperium-backend`. |
| CWD strict | `_assert_safe_claude_invocation(...)` impose `cwd == worktree_path`. |
| Worktree borné | `_assert_safe_claude_invocation(...)` impose que `worktree_path` soit sous `SESSIONS_ROOT`. |
| Arguments Claude filtrés | Les arguments opérationnels contenant `/opt/imperium-backend` sont refusés. |
| Pas de shell | `subprocess.Popen(..., shell=False)`. |
| Pas d'entrée interactive | `stdin=subprocess.DEVNULL`. |

Exemple de refus attendu :

```text
session_id = "../escape"  → ValueError
worktree_path = /opt/imperium-backend/... → refus
cwd != worktree_path → refus
argv opérationnel contenant /opt/imperium-backend → refus
```

## 9. Preview et exposition réseau

La preview est lancée par `start_design_preview(...)` depuis le worktree de session.

Le code choisit l'hôte public par `preview_public_host_detailed()`, qui appelle `_detect_preview_public_host()` :

```text
1. tailscale ip -4
2. hostname -I
3. tower.local
```

Règle d'exploitation F12 : la preview destinée à la validation humaine doit être consommée via l'adresse Tailscale. Les serveurs de design ne doivent pas être exposés publiquement hors réseau contrôlé.

État réel du code au 2026-06-04 : le code préfère Tailscale, mais conserve un fallback LAN puis `tower.local` si Tailscale est absent ou indisponible. Ce fallback est utile pour développement local, mais ne doit pas être traité comme une garantie stricte "Tailscale uniquement" tant qu'un refus explicite des fallbacks n'est pas ajouté.

Format d'URL :

```text
http://<preview_host>:<port>/?session=<session_id>
```

Ports de base par app :

```text
imperium: 5173
vault:    5174
vector:   5175
pulse:    5176
path:     5177
```

## 10. Exécution Claude

`run_claude_design_in_worktree(...)` est le seul point qui invoque la CLI Claude.

Le mode d'exécution réel est contrôlé par :

```text
DESIGN_CLAUDE_EXECUTION_ENABLED
```

Valeur par défaut dans `/opt/orchestrator/config.py` :

```text
False
```

Quand le toggle est désactivé, la session prépare le worktree et retourne un état `worktree_ready`. Quand il est activé, Claude tourne dans le worktree en tâche de fond et les logs sont écrits dans :

```text
claude_stdout.log
claude_stderr.log
```

Les flags Claude candidats sont détectés via `claude --help` avant usage. Le code ne les ajoute pas aveuglément.

Flags candidats vérifiés :

```text
--add-dir
--allowedTools
--permission-mode
--output-format
--include-partial-messages
--max-budget-usd
--system-prompt
```

Outils autorisés si `--allowedTools` est supporté :

```text
Read
Grep
Glob
Write
Edit
```

## 11. Limites MVP

Le pipeline design ne doit pas :

- modifier `/opt/imperium-backend` ;
- créer de logique métier canonique côté frontend ;
- brancher une API backend sans validation visuelle ;
- lancer des actions n8n ;
- écrire dans PostgreSQL ;
- créer une décision AI canonique ;
- remplacer les règles produit Imperium, Vault, Vector, Pulse ou Path.

Le rôle du pipeline est de produire une interface inspectable, dans un worktree isolé, avant validation humaine.

## 12. État des tests

Au moment de la rédaction, la couverture annoncée pour le périmètre orchestrateur/design est de **132 tests pytest**. Aucun test n'a été lancé pour produire ce document.

Les fichiers de tests pertinents visibles dans `/opt/orchestrator/tests/` sont :

```text
test_asset_manager_server.py
test_claude_design_runner.py
test_claude_runner.py
test_codex_runner.py
test_design_toggle_config.py
test_logger.py
test_runtime_hardening.py
```

Le fichier principal pour ce pipeline est :

```text
/opt/orchestrator/tests/test_claude_design_runner.py
```

Il couvre notamment :

- la génération de `CLAUDE.md` avec assets, polices, textures et règles strictes ;
- la technique `@font-face` ;
- la technique des titres dorés avec `background-clip` ;
- la création du worktree et de la branche `design/<sid>` ;
- le refus des `session_id` dangereux ;
- le refus des chemins sous `/opt/imperium-backend` ;
- le refus d'un `cwd` différent du worktree ;
- la sélection préférentielle de l'adresse Tailscale pour les preview URLs ;
- les fallbacks LAN et `tower.local` ;
- l'exécution Claude confinée au worktree ;
- les logs `claude_stdout.log`, `claude_stderr.log`, `preview_stdout.log`, `preview_stderr.log`.

Tests exacts vérifiés dans ce fichier :

```text
test_generate_design_claude_md_lists_assets_and_strict_rules
test_generate_design_claude_md_lists_fonts_and_gold_title_technique
test_assets_and_claude_md_for_app_without_assets_do_not_crash
test_prepare_worktree_creates_branch_and_dir
test_prepare_worktree_refuses_when_workspace_missing
test_prepare_worktree_refuses_duplicate_worktree
test_prepare_worktree_rejects_unknown_app
test_prepare_worktree_rejects_unsafe_session_id
test_branch_and_preview_url_helpers_use_selected_preview_host
test_detect_preview_public_host_prefers_tailscale_ip
test_detect_preview_public_host_falls_back_to_lan_ip
test_detect_preview_public_host_falls_back_to_tower_local
test_guard_refuses_argv_referencing_imperium_backend
test_guard_refuses_cwd_different_from_worktree
test_guard_refuses_worktree_outside_sessions_root
test_guard_refuses_worktree_pointing_at_imperium_backend
test_guard_refuses_worktree_under_imperium_backend
test_ensure_workspace_refuses_frontend_app_dir_under_imperium_backend
test_run_in_worktree_refuses_worktree_outside_sessions_root
test_start_preview_uses_worktree_cwd_host_and_port
test_start_preview_refuses_imperium_backend_worktree
```

## 13. Definition of Done F12

Ce document est complet si :

| Critère | Required |
|---|---|
| Fonction `generate_design_claude_md` nommée exactement | YES |
| Rôle du `CLAUDE.md` par worktree expliqué | YES |
| Assets, polices, textures et titres dorés documentés | YES |
| Règles anti-placeholder documentées | YES |
| Isolation worktree documentée | YES |
| Path traversal documenté | YES |
| Interdiction backend monorepo documentée | YES |
| Preview Tailscale et état réel du fallback documentés | YES |
| État des tests et fichiers pytest documentés | YES |

