# pilotagent — streaming gRPC via tunnel SSH

`pilotagent` expose un service gRPC `Metrics/StreamCpu` qui diffuse l'utilisation CPU
en continu. L'agent écoute sur `127.0.0.1:50051` par défaut, ce qui signifie qu'il
n'est pas accessible depuis le réseau — seul un tunnel SSH permet d'y accéder depuis
la machine locale.

## Démarrer l'agent sur la machine distante

```bash
# Compiler et déposer le binaire sur la machine cible
go build -o pilotagent ./cmd/pilotagent
scp pilotagent user@host:/usr/local/bin/pilotagent

# Démarrer en mode gRPC (écoute sur 127.0.0.1:50051 par défaut)
ssh user@host "pilotagent -mode grpc"
```

## Ouvrir le tunnel SSH

```bash
# Rediriger le port local 50051 vers 127.0.0.1:50051 sur la machine distante
ssh -L 50051:127.0.0.1:50051 -N user@host
```

Le tunnel reste ouvert tant que la commande `ssh -L` tourne. Fermez-le avec `Ctrl+C`.

## Consommer le flux depuis Python

```python
from pilotremote.metrics_client import MetricsClient

client = MetricsClient("127.0.0.1:50051")
for sample in client.stream_cpu(interval_seconds=1.0):
    print(f"{sample.timestamp_ms} ms  →  {sample.usage_percent:.1f} %")
```

## Options de l'agent

| Flag | Défaut | Description |
|------|--------|-------------|
| `-mode` | `json` | `json` : sortie stdout, `grpc` : serveur gRPC |
| `-addr` | `127.0.0.1:50051` | Adresse d'écoute gRPC |
| `-interval` | `1s` | Intervalle d'échantillonnage (mode json) |
| `-samples` | `0` | Nombre d'échantillons (0 = infini, mode json) |
| `-proc-stat` | `/proc/stat` | Chemin vers le fichier de statistiques CPU |

## Architecture du flux

```
machine distante                     machine locale
┌────────────────────┐               ┌──────────────────────┐
│  pilotagent        │               │  Python (pilot)      │
│  127.0.0.1:50051   │◄─SSH tunnel──►│  MetricsClient       │
│  StreamCpu (gRPC)  │               │  127.0.0.1:50051     │
└────────────────────┘               └──────────────────────┘
```

## Contrat Protobuf

Le contrat source est versionné dans `proto/pilotmetrics.proto`.
Les stubs générés sont commités dans :

- Go : `agents/pilotagent/gen/pilotmetrics/v1alpha1/`
- Python : `packages/pilotremote/src/pilotremote/gen/`

Pour regénérer les stubs après modification du proto :

```bash
# Go
protoc --proto_path=proto \
  --go_out=agents/pilotagent/gen/pilotmetrics/v1alpha1 --go_opt=paths=source_relative \
  --go-grpc_out=agents/pilotagent/gen/pilotmetrics/v1alpha1 --go-grpc_opt=paths=source_relative \
  proto/pilotmetrics.proto

# Python
python -m grpc_tools.protoc --proto_path=proto \
  --python_out=packages/pilotremote/src/pilotremote/gen \
  --grpc_python_out=packages/pilotremote/src/pilotremote/gen \
  proto/pilotmetrics.proto
# Corriger l'import dans pilotmetrics_pb2_grpc.py :
# import pilotmetrics_pb2 → from pilotremote.gen import pilotmetrics_pb2
```
