# Release

## Table des matieres

- [Version](#version)
- [Commits](#commits)
- [Checks GitHub](#checks-github)
- [Bump local](#bump-local)
- [Release automatique](#release-automatique)
- [Publication GitHub Packages](#publication-github-packages)

## Version

Le depot utilise une version unique synchronisee pour tous les paquets du
monorepo :

- `k3s-workspace`
- `k3splan`
- `k3sremote`
- `k3scli`

Les versions sont mises a jour ensemble par Commitizen.

L'agent Go dans `agents/k3sagent` suit la meme version produit que les paquets
Python tant qu'il reste pilote par `k3sctl`. Si l'agent devient un composant
autonome avec son propre cycle de release, la strategie de version devra etre
separee explicitement.

Le message du commit de release est fixe par Commitizen :

```text
chore(release): v$current_version to v$new_version
```

Le workflow de release ignore les commits qui commencent par `chore(release):`
pour eviter une boucle infinie apres le push du bump.

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

Les messages de commit ne doivent pas contenir de courriel, de marque ou de nom
d'outil IA. La meme regle s'applique aux titres et corps de PR.

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
cd agents/k3sagent
go test ./...
go build ./cmd/k3sagent
cd ../..
docker build -f agents/k3sagent/Dockerfile .
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

## Release automatique

Le workflow `.github/workflows/release.yml` se lance automatiquement sur push
vers `main`, donc apres merge d'une PR. Il reste aussi declenchable manuellement
via `workflow_dispatch`.

En mode automatique, Commitizen determine l'increment a partir des commits
Conventional Commits depuis le dernier tag. Le workflow utilise
`--allow-no-commit` pour produire une release meme si la PR mergee ne contient
pas de commit normalement eligible.

En mode manuel, le workflow accepte un input `bump` :

- `auto` : laisse Commitizen determiner l'increment ;
- `patch` ;
- `minor` ;
- `major`.

Le workflow :

1. installe l'environnement avec `uv` ;
2. lance les checks complets ;
3. execute `uv run cz bump --yes --allow-no-commit` ou
   `uv run cz bump --yes --increment <bump>` ;
4. met a jour les versions et `CHANGELOG.md` ;
5. pousse le commit de bump et le tag vers `main` ;
6. build les distributions avec
   `uv build --all-packages --out-dir dist --clear --no-create-gitignore` ;
7. build l'agent Go dans `dist/k3sagent` ;
8. publie l'image de l'agent sur GitHub Packages via GHCR ;
9. cree une GitHub Release avec les artefacts de `dist/`.

## Publication GitHub Packages

GitHub Packages ne fournit pas de registre PyPI pour packages Python. Les
distributions Python sont donc attachees a la GitHub Release comme artefacts,
mais ne sont pas publiees dans GitHub Packages.

L'agent Go est publie sur GitHub Packages sous forme d'image OCI dans le GitHub
Container Registry :

```text
ghcr.io/<owner>/k3sagent:<version>
ghcr.io/<owner>/k3sagent:latest
```

La GitHub Release contient aussi :

- les wheels et sdists Python ;
- le binaire Go `k3sagent`.
