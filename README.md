# k3s

Outil declaratif experimental pour inspecter, planifier et reconciler l'etat k3s
d'une machine distante.

## Architecture

Le depot est un monorepo pilote principalement par Python et `uv` :

- `packages/k3splan` contient le moteur declaratif ;
- `packages/k3sremote` contient les adaptateurs distants, notamment SSH ;
- `packages/k3scli` expose le CLI `k3sctl`.

Le CLI doit couvrir trois usages : un mode commande explicite, un mode CI
non interactif avec sorties stables, et un mode smart qui observe l'etat actuel,
compare avec l'etat desire et propose les prochaines actions possibles.

Le choix retenu pour les metriques continues est de garder l'application et le
CLI en Python, et d'ajouter si besoin un agent distant en Go dans le meme
monorepo. L'agent vivrait dans `agents/k3sagent`, exposerait une API gRPC locale
sur la machine distante, et partagerait ses contrats Protobuf avec le client
Python.

Ce modele permet de deployer un binaire Go simple sur la machine distante tout en
gardant l'orchestration, les manifests et l'experience CLI dans Python. Si la
seule connexion disponible est SSH, le client Python accede a l'agent via un
tunnel SSH vers `127.0.0.1` sur la machine distante.

## Developpement

Installer l'environnement :

```bash
uv sync --all-packages --dev
```

Lancer le CLI :

```bash
uv run k3sctl --help
uv run k3sctl validate examples/single-server.yaml
uv run k3sctl validate examples/single-server.yaml --inventory examples/inventory.example.yaml
uv run k3sctl plan examples/single-server.yaml
uv run k3sctl inspect examples/single-server.yaml --inventory inventory.local.yaml
uv run k3sctl apply examples/single-server.yaml --inventory inventory.local.yaml
uv run k3sctl doctor examples/single-server.yaml --inventory inventory.local.yaml
uv run k3sctl drift examples/single-server.yaml --inventory inventory.local.yaml
uv run k3sctl journal list
```

Configurer un contexte local :

```bash
uv run k3sctl context set dev examples/single-server.yaml inventory.local.yaml
uv run k3sctl context list
uv run k3sctl context show
uv run k3sctl inspect
uv run k3sctl plan
```

Travailler avec plusieurs contextes :

```bash
uv run k3sctl context set prod examples/prod.yaml inventory.prod.yaml
uv run k3sctl context use prod
uv run k3sctl inspect
```

Utiliser Cilium comme CNI (a la place de Flannel) :

```bash
uv run k3sctl validate examples/cilium-server.yaml --inventory inventory.local.yaml
uv run k3sctl plan examples/cilium-server.yaml --inventory inventory.local.yaml
```

Les manifestes publics utilisent `spec.connectionRef`. Les vraies informations
de connexion sont a placer dans `inventory.local.yaml`, ignore par Git.

Creer un inventaire local :

```bash
cp examples/inventory.example.yaml inventory.local.yaml
```

Puis remplacer les valeurs d'exemple par les vraies informations de connexion.

Verifier le depot :

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy packages
uv run pytest
```

Verifier l'agent Go :

```bash
cd agents/k3sagent
go test ./...
go build ./cmd/k3sagent
./k3sagent --samples 1
```

Installer les hooks Git :

```bash
uv run pre-commit install --hook-type pre-commit
uv run pre-commit install --hook-type pre-push
uv run pre-commit install --hook-type commit-msg
```

Lancer les hooks manuellement :

```bash
uv run pre-commit run --all-files
uv run pre-commit run --hook-stage pre-push --all-files
```

Gestion de version :

```bash
uv run cz bump --dry-run --yes
uv run cz bump
```

Les checks GitHub lancent format, lint, typage, tests et builds sur les pull
requests et sur `main`. La release est automatique apres merge sur `main` :
Commitizen bump la version, met a jour `CHANGELOG.md`, publie l'image de l'agent
sur GitHub Packages via GHCR et cree la GitHub Release avec les distributions
Python en artefacts.

## Documentation

- [Instructions pour agents IA](AGENTS.md)
- [Architecture](docs/architecture.md)
- [Plan](docs/plan.md)
- [Manifestes et inventaires](docs/manifest.md)
- [Release](docs/release.md)
