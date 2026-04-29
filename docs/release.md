# Release

## Table des matieres

- [Version](#version)
- [Commits](#commits)
- [Checks GitHub](#checks-github)
- [Bump local](#bump-local)
- [Release GitHub](#release-github)
- [Publication PyPI](#publication-pypi)

## Version

Le depot utilise une version unique synchronisee pour tous les paquets du
monorepo :

- `k3s-workspace`
- `k3splan`
- `k3sremote`
- `k3scli`

Les versions sont mises a jour ensemble par Commitizen.

L'agent Go prevu dans `agents/k3sagent` n'existe pas encore. Tant qu'il reste
pilote par `k3sctl`, il doit suivre la meme version produit que les paquets
Python. Si l'agent devient un composant autonome avec son propre cycle de
release, la strategie de version devra etre separee explicitement.

## Commits

Les messages de commit suivent Conventional Commits :

```text
feat: add manifest validation
fix: handle missing k3s binary
docs: document rollback guarantees
test: add planner tests
refactor: split action model
chore: update dependencies
```

Effet sur la version :

```text
fix:      patch
feat:     minor
BREAKING: major
```

Tant que le projet reste en `0.x`, `major_version_zero = true` limite les bumps
majeurs automatiques.

## Checks GitHub

Le workflow `.github/workflows/checks.yml` s'execute sur :

- les pull requests ;
- les pushes vers `main`.

Il lance :

```bash
uv sync --all-packages --dev --frozen
uv run ruff format --check .
uv run ruff check .
uv run mypy packages
uv run pytest
```

## Bump local

Verifier le depot :

```bash
uv run pre-commit run --all-files
uv run pre-commit run --hook-stage pre-push --all-files
```

Previsualiser le prochain bump :

```bash
uv run cz bump --dry-run --yes
```

Creer la release :

```bash
uv run cz bump
git push
git push --tags
```

Commitizen met a jour :

- les versions des `pyproject.toml` ;
- `CHANGELOG.md` ;
- le tag Git `vX.Y.Z`.

## Release GitHub

Le workflow `.github/workflows/release.yml` est manuel via `workflow_dispatch`.
Il doit etre lance depuis la branche `main`. Il accepte un input `bump` :

- `auto` : laisse Commitizen determiner l'increment ;
- `patch` ;
- `minor` ;
- `major`.

Le workflow :

1. installe l'environnement avec `uv` ;
2. lance les checks complets ;
3. execute `uv run cz bump --yes` ou `uv run cz bump --yes --increment <bump>` ;
4. pousse le commit de bump et le tag vers `main` ;
5. build les distributions avec
   `uv build --all-packages --out-dir dist --clear --no-create-gitignore` ;
6. publie les distributions sur PyPI ;
7. cree une GitHub Release avec les artefacts de `dist/`.

## Publication PyPI

La publication utilise `pypa/gh-action-pypi-publish` avec Trusted Publishing.
Le repository doit etre configure cote PyPI avec un publisher lie a :

- owner/repository GitHub du projet ;
- workflow `.github/workflows/release.yml` ;
- environnement GitHub `pypi`.

Aucun token PyPI ne doit etre stocke dans le depot.
