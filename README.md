# k3s

Outil declaratif experimental pour inspecter, planifier et reconciler l'etat k3s
d'une machine distante.

Le depot contient le CLI `k3sp`, son moteur de planification, les adaptateurs
d'execution distante, la documentation du projet et les premieres briques d'un
agent distant pour les metriques continues.

## Contenu

- `packages/pilotplan` : moteur declaratif, modeles, planification, runner,
  journal et sante.
- `packages/pilotremote` : adaptateurs systeme et execution distante.
- `packages/pilotcli` : interface en ligne de commande `k3sp`.
- `agents/pilotagent` : agent Go experimental pour les metriques continues.
- `proto` : contrats partages.
- `examples` : exemples de manifestes et d'inventaires.
- `docs` : documentation longue.

## Documentation

- [Contribuer](CONTRIBUTING.md)
- [Architecture](docs/architecture.md)
- [Plan](docs/plan.md)
- [Manifestes et inventaires](docs/manifest.md)
- [Release](docs/release.md)
