# Contribuer

Ce fichier donne le contexte minimal pour travailler dans ce depot sans casser
les conventions locales.

## Contexte projet

`k3sp` est un outil declaratif experimental pour inspecter, planifier et
reconcilier l'etat k3s d'une machine distante.

Le modele mental est :

```text
desired state -> observed state -> plan -> action -> verify -> commit/rollback
```

## Structure

- `packages/pilotplan` : moteur declaratif pur, modeles, planification, runner,
  journal et sante.
- `packages/pilotremote` : adaptateurs systeme et execution distante, notamment
  SSH.
- `packages/pilotcli` : CLI `k3sp`, commandes Typer et affichage Rich.
- `docs/architecture.md` : architecture cible.
- `docs/plan.md` : phasage du projet.
- `docs/manifest.md` : manifestes et inventaires.
- `docs/release.md` : versionnement et release.
- `agents/pilotagent` : agent Go experimental pour les metriques continues.
- `proto/pilotmetrics.proto` : contrat Protobuf source pour les futurs flux gRPC.
- `.github/workflows/checks.yml` : checks GitHub Actions.
- `.github/workflows/release.yml` : release automatique sur `main`, bump,
  changelog, publication GHCR et GitHub Release.

## Regles de contribution

- Ne pas committer directement sur `main` ou `master`; creer une branche de
  travail.
- Ne jamais ajouter de courriel dans un message de commit. Ne pas utiliser de
  `Co-authored-by`, `Signed-off-by`, trailers, corps de commit ou exemples qui
  contiennent une adresse courriel.
- Ne jamais ajouter de marque commerciale dans les metadonnees de contribution :
  titres de PR, corps de PR, messages de commit, trailers ou prefixes.
- Ne pas versionner de secrets, d'adresses internes, de kubeconfigs ou
  d'inventaires locaux.
- Garder `pilotplan` independant de SSH, du CLI et des effets de bord systeme.
- Respecter les trois modes cibles du CLI : commande explicite, CI non
  interactif et smart assiste par `desired + observed`.
- Preferer des changements scopes, alignes avec les patterns existants.
- Eviter les refactors opportunistes non lies a la tache.
- Mettre a jour la documentation quand un comportement utilisateur, un contrat
  ou une commande change.

## Commandes utiles

Installer l'environnement :

```bash
uv sync --all-packages --dev
```

Verifier le depot :

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy packages
uv run pytest
```

Lancer le CLI :

```bash
uv run k3sp --help
uv run k3sp validate examples/single-server.yaml
uv run k3sp plan examples/single-server.yaml
uv run k3sp inspect examples/single-server.yaml --inventory inventory.local.yaml
```

Installer les hooks :

```bash
uv run pre-commit install --hook-type pre-commit
uv run pre-commit install --hook-type pre-push
uv run pre-commit install --hook-type commit-msg
```

## Tests et qualite

- Les tests Python vivent sous `packages/**/tests`.
- `ruff` gere le lint et le formatage.
- `mypy` est strict et configure avec les chemins `packages/*/src`.
- Les hooks `pre-push` lancent `mypy` et `pytest`.
- Le hook `pre-commit` bloque les commits sur `main`, `master` ou en HEAD
  detache.
- Le hook `commit-msg` refuse les messages contenant une adresse courriel avant
  la verification Commitizen.
- Le hook `commit-msg` refuse les marques commerciales dans les messages de
  commit via `scripts/check_metadata.py`.
- Le workflow `.github/workflows/metadata.yml` applique la meme regle aux titres
  de PR, corps de PR et messages de commits de la PR.
- Les checks GitHub doivent rester alignes avec les commandes locales :
  `ruff format --check`, `ruff check`, `mypy packages` et `pytest`.
- Les checks Go doivent rester alignes avec `go test ./...` et
  `go build ./cmd/pilotagent` depuis `agents/pilotagent`.
- Le workflow de release se lance automatiquement sur `main` et ignore les
  commits `chore(release):` pour eviter une boucle.
- GitHub Packages ne supporte pas de registre PyPI. Publier l'agent Go comme
  image GHCR et attacher les distributions Python a la GitHub Release.

## Connexions distantes

Les manifestes publics doivent utiliser `spec.connectionRef`. Les informations
reelles de connexion vont dans `inventory.local.yaml` ou `*.local.yaml`, ignores
par Git.

Pour les exemples publics, utiliser :

```bash
uv run k3sp validate examples/single-server.yaml --inventory examples/inventory.example.yaml
```

## Style documentaire

- Les documents longs doivent avoir une table des matieres.
- Garder les exemples executables et coherents avec le README.
- Utiliser des chemins relatifs depuis la racine du depot.
- Le plan projet vit dans `docs/plan.md`, pas dans `docs/architecture.md`.
