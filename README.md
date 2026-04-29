# k3s

Outil declaratif experimental pour inspecter, planifier et reconciler l'etat k3s
d'une machine distante.

Le depot contient le CLI `k3sctl`, son moteur de planification, les adaptateurs
d'execution distante, la documentation du projet et les premieres briques d'un
agent distant pour les metriques continues.

## Contenu

- `packages/k3splan` : moteur declaratif, modeles, planification, runner,
  journal et sante.
- `packages/k3sremote` : adaptateurs systeme et execution distante.
- `packages/k3scli` : interface en ligne de commande `k3sctl`.
- `agents/k3sagent` : agent Go experimental pour les metriques continues.
- `proto` : contrats partages.
- `examples` : exemples de manifestes et d'inventaires.
- `docs` : documentation longue.

## Documentation

- [Contribuer](CONTRIBUTING.md)
- [Architecture](docs/architecture.md)
- [Plan](docs/plan.md)
- [Manifestes et inventaires](docs/manifest.md)
- [Release](docs/release.md)
