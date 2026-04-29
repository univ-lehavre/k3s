# cluster-pilot

[![DOI](https://zenodo.org/badge/1223607555.svg)](https://doi.org/10.5281/zenodo.19880066)
[![Version](https://img.shields.io/github/v/release/univ-lehavre/cluster-pilot)](https://github.com/univ-lehavre/cluster-pilot/releases/latest)

Outil declaratif experimental pour inspecter, planifier et reconciler l'etat k3s
d'une machine distante.

Le depot contient le CLI `pilot`, son moteur de planification, les adaptateurs
d'execution distante, la documentation du projet et un agent Go distant pour
streamer les metriques systeme via gRPC sur tunnel SSH.

## Contenu

- `packages/pilotplan` : moteur declaratif, modeles, planification, runner,
  journal et sante.
- `packages/pilotremote` : adaptateurs systeme et execution distante.
- `packages/pilotcli` : interface en ligne de commande `pilot`.
- `agents/pilotagent` : agent Go pour le streaming gRPC de metriques systeme.
- `proto` : contrats partages.
- `examples` : exemples de manifestes et d'inventaires.
- `docs` : documentation longue.

## Documentation

- [Contribuer](CONTRIBUTING.md)
- [Tester avec Multipass](docs/testing-multipass.md)
- [Architecture](docs/architecture.md)
- [Plan](docs/plan.md)
- [Manifestes et inventaires](docs/manifest.md)
- [Agent gRPC et tunnel SSH](docs/agent-grpc.md)
- [Release](docs/release.md)
