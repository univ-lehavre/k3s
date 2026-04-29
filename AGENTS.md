# Instructions pour agents IA

Ce fichier donne le contexte minimal pour travailler dans ce depot sans casser
les conventions locales.

## Contexte projet

`k3sctl` est un outil declaratif experimental pour inspecter, planifier et
reconcilier l'etat k3s d'une machine distante.

Le modele mental est :

```text
desired state -> observed state -> plan -> action -> verify -> commit/rollback
```

## Structure

- `packages/k3splan` : moteur declaratif pur, modeles, planification, runner,
  journal et sante.
- `packages/k3sremote` : adaptateurs systeme et execution distante, notamment
  SSH.
- `packages/k3scli` : CLI `k3sctl`, commandes Typer et affichage Rich.
- `docs/architecture.md` : architecture cible.
- `docs/plan.md` : phasage du projet.
- `docs/manifest.md` : manifestes et inventaires.
- `docs/release.md` : versionnement et release.
- `.github/workflows/checks.yml` : checks GitHub Actions.
- `.github/workflows/release.yml` : bump, build, publication PyPI et GitHub
  Release.

Une extension future prevoit un agent Go dans `agents/k3sagent` avec contrats
Protobuf dans `proto/`. Cet outillage n'existe pas encore.

## Regles de contribution

- Ne pas committer directement sur `main` ou `master`; creer une branche de
  travail.
- Ne jamais ajouter de courriel dans un message de commit. Ne pas utiliser de
  `Co-authored-by`, `Signed-off-by`, trailers, corps de commit ou exemples qui
  contiennent une adresse courriel.
- Ne pas versionner de secrets, d'adresses internes, de kubeconfigs ou
  d'inventaires locaux.
- Garder `k3splan` independant de SSH, du CLI et des effets de bord systeme.
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
uv run k3sctl --help
uv run k3sctl validate examples/single-server.yaml
uv run k3sctl plan examples/single-server.yaml
uv run k3sctl inspect examples/single-server.yaml --inventory inventory.local.yaml
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
- Les checks GitHub doivent rester alignes avec les commandes locales :
  `ruff format --check`, `ruff check`, `mypy packages` et `pytest`.
- Le workflow de release doit rester manuel et ne doit pas stocker de token PyPI
  dans le depot. Utiliser Trusted Publishing avec l'environnement GitHub `pypi`.

## Connexions distantes

Les manifestes publics doivent utiliser `spec.connectionRef`. Les informations
reelles de connexion vont dans `inventory.local.yaml` ou `*.local.yaml`, ignores
par Git.

Pour les exemples publics, utiliser :

```bash
uv run k3sctl validate examples/single-server.yaml --inventory examples/inventory.example.yaml
```

## Style documentaire

- Les documents longs doivent avoir une table des matieres.
- Garder les exemples executables et coherents avec le README.
- Utiliser des chemins relatifs depuis la racine du depot.
- Le plan projet vit dans `docs/plan.md`, pas dans `docs/architecture.md`.
