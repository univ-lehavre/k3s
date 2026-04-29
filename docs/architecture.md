# pilot - Architecture

## Table des matieres

- [Objectif](#objectif)
- [Choix techniques](#choix-techniques)
- [Organisation du depot](#organisation-du-depot)
- [Agent distant Go](#agent-distant-go)
- [CLI cible](#cli-cible)
- [Modes CLI](#modes-cli)
- [Contrats du moteur](#contrats-du-moteur)
- [Rollback](#rollback)
- [Manifeste d'installation](#manifeste-dinstallation)
- [Manifeste de desinstallation](#manifeste-de-desinstallation)
- [Inventaire prive](#inventaire-prive)
- [Exemple de plan](#exemple-de-plan)
- [Plan](#plan)

## Objectif

Construire un outil declaratif permettant de piloter l'etat d'une machine distante pour installer, desinstaller, verifier et maintenir k3s.

Le moteur doit permettre de :

- declarer un etat cible complexe dans un manifeste YAML ;
- observer l'etat reel d'une machine distante ;
- produire une liste ordonnee d'actions a operer ;
- lancer les actions une par une ou en lot ;
- verifier que chaque action a bien produit l'effet attendu ;
- declencher un rollback si la verification echoue ;
- journaliser les executions pour audit, reprise et rollback.

Le modele mental est :

```text
desired state -> observed state -> plan -> action -> verify -> commit/rollback
```

## Choix techniques

Le projet part sur Python avec `uv` comme gestionnaire de paquet et de workspace.

Stack initiale :

- `uv` pour l'environnement, le lockfile et le workspace ;
- `pydantic` pour valider les manifestes ;
- `ruamel.yaml` pour lire et ecrire du YAML ;
- `typer` pour le CLI ;
- `rich` pour l'affichage des plans, journaux et rapports de sante ;
- `fabric` ou `paramiko` pour SSH ;
- `pytest` pour les tests ;
- `ruff` pour lint et format ;
- `mypy` pour le typage statique.

La distribution cible initiale est un outil lance depuis un poste ou une machine d'administration.

Extension pour les metriques continues :

- un agent distant ecrit en Go, livre comme binaire autonome ;
- un contrat Protobuf partage entre l'agent Go et le client Python ;
- gRPC pour les flux de metriques, par exemple CPU, memoire, disque et reseau ;
- SSH comme transport d'administration et, si necessaire, comme tunnel vers
  l'agent distant.

Cette extension reste dans le meme monorepo tant que l'agent est pilote par
`pilot` et evolue avec son client Python. Un depot separe ne devient preferable
que si l'agent obtient son propre cycle de release, plusieurs consommateurs
independants, ou une compatibilite inter-versions longue duree.

## Organisation du depot

Le depot est un monorepo `uv workspace`, avec des paquets separes par responsabilite.
Il est polyglotte : les paquets Python restent sous `packages/`, et l'agent Go
vit dans une zone dediee pour ne pas melanger les responsabilites.

```text
k3s/
  pyproject.toml
  uv.lock
  README.md

  packages/
    pilotplan/
      src/pilotplan/
        desired.py
        observed.py
        planner.py
        actions/
        runner.py
        journal.py
      tests/

    pilotremote/
      src/pilotremote/
        ssh.py
        systemd.py
        files.py
        packages.py
      tests/

    pilotcli/
      src/pilotcli/
        app.py
        commands/
      tests/

  agents/
    pilotagent/
      go.mod
      cmd/pilotagent/
        main.go
      internal/

  proto/
    pilotmetrics.proto

  examples/
    single-server.yaml
    uninstall.yaml
    inventory.example.yaml

  docs/
    architecture.md
    manifest.md
```

Responsabilites :

- `pilotplan` contient le moteur declaratif pur : manifestes, etat observe, planification, actions, runner, journal ;
- `pilotremote` contient les adaptateurs systeme : SSH, systemd, fichiers distants, commandes k3s ;
- `pilotcli` contient l'interface utilisateur : commandes Typer, affichage Rich, options CLI.
- `agents/pilotagent` contient l'agent Go deployable sur la machine distante pour les metriques continues ;
- `proto` contient les contrats Protobuf partages entre Go et Python.

Regle de dependance :

```text
pilotcli -> pilotplan + pilotremote
pilotremote -> pilotplan si besoin de types communs
pilotplan -> aucune dependance vers CLI ou SSH
pilotagent -> contrats proto + bibliotheques Go standard ou internes
client Python gRPC -> code genere depuis proto
```

Le coeur doit rester testable sans machine distante.

## Agent distant Go

L'agent Go est une extension optionnelle destinee aux flux continus, la ou une
commande SSH ponctuelle est moins adaptee.

Objectifs :

- fournir un binaire unique facile a copier sur la machine distante ;
- exposer une API gRPC locale, ecoutee sur `127.0.0.1` ;
- streamer les metriques systeme avec un contrat stable ;
- eviter d'installer un environnement Python complet sur la machine distante.

Modele de connexion :

```text
application Python locale
  -> localhost:50051
  -> tunnel SSH
  -> machine distante:127.0.0.1:50051
  -> agent Go
```

Le service gRPC ne doit pas etre expose publiquement par defaut. Si la seule
connexion autorisee est SSH, `pilot` ouvre ou documente un tunnel local avant de
se connecter au service.

Contrat initial envisage :

```proto
syntax = "proto3";

package k3s.metrics.v1alpha1;

service Metrics {
  rpc StreamCpu(CpuRequest) returns (stream CpuSample);
}

message CpuRequest {
  double interval_seconds = 1;
}

message CpuSample {
  double usage_percent = 1;
  int64 timestamp_ms = 2;
}
```

Les fichiers generes Go et Python ne sont pas le contrat source. Le fichier
`.proto` fait autorite.

## CLI cible

Le binaire s'appelle `pilot`.

Gestion des contextes :

```bash
pilot context set <name> <manifest> <inventory>
pilot context use <name>
pilot context list
pilot context show
```

Commandes initiales :

```bash
pilot inspect examples/single-server.yaml --inventory inventory.local.yaml
pilot plan examples/single-server.yaml
pilot apply examples/single-server.yaml
pilot verify examples/single-server.yaml
pilot rollback --run-id <run-id>
pilot journal
```

Commandes utiles ensuite :

```bash
pilot apply examples/single-server.yaml --inventory inventory.local.yaml --step
pilot apply examples/single-server.yaml --inventory inventory.local.yaml --from action.install-k3s
pilot drift examples/single-server.yaml --inventory inventory.local.yaml
pilot doctor examples/single-server.yaml --inventory inventory.local.yaml
```

## Modes CLI

`pilot` doit couvrir trois modes d'usage complementaires.

### Mode commande

Le mode commande est le mode CLI explicite actuel. L'utilisateur choisit une
commande et ses arguments :

```bash
pilot validate examples/single-server.yaml
pilot inspect examples/single-server.yaml --inventory inventory.local.yaml
pilot plan examples/single-server.yaml --inventory inventory.local.yaml
pilot apply examples/single-server.yaml --inventory inventory.local.yaml
```

Ce mode privilegie la predictibilite et la composabilite shell.

### Mode CI

Le mode CI est non interactif et stable pour l'automatisation.

Objectifs :

- aucune question interactive ;
- sorties machine-readable, en particulier JSON ;
- codes de sortie documentes ;
- erreurs concises sur `stderr` ;
- options explicites pour refuser les actions destructives ou imposer un
  `--dry-run`.

Commandes ciblees :

```bash
pilot ci validate --manifest examples/single-server.yaml
pilot ci inspect --manifest examples/single-server.yaml --inventory inventory.local.yaml --output json
pilot ci plan --manifest examples/single-server.yaml --inventory inventory.local.yaml --output json
pilot ci drift --manifest examples/single-server.yaml --inventory inventory.local.yaml
```

### Mode smart

Le mode smart assiste l'utilisateur a partir de l'etat desire et de l'etat
observe. Il inspecte la machine, construit le plan, puis propose les actions
pertinentes au lieu d'obliger l'utilisateur a connaitre la prochaine commande.

Exemples d'intentions :

- aucun contexte actif : proposer `context set` ;
- manifeste invalide : proposer `validate` et afficher les corrections ;
- SSH indisponible : proposer les checks de connexion ;
- derive detectee : proposer `plan`, `apply --dry-run`, puis `apply` ;
- machine saine : proposer `doctor`, `drift` ou surveillance.

Commande cible :

```bash
pilot smart
pilot smart examples/single-server.yaml --inventory inventory.local.yaml
```

Le mode smart reste explicable : chaque proposition doit indiquer pourquoi elle
est proposee, son niveau de risque, et la commande concrete equivalente.

## Contrats du moteur

### DesiredState

Representation validee du manifeste YAML.

Responsabilites :

- charger un manifeste ;
- valider `apiVersion`, `kind`, `metadata` et `spec` ;
- verifier que `spec` definit exactement une source de connexion ;
- exposer un modele Python type.

La source de connexion est soit :

- `spec.connectionRef`, recommande pour les depots publics ;
- `spec.connection`, reserve aux usages prives ou aux tests.

### Inventory

Representation des connexions locales non versionnees.

Responsabilites :

- charger un inventaire YAML ;
- exposer les connexions nommees ;
- permettre la resolution d'un `connectionRef`.

### ObservedState

Representation de l'etat reel observe sur la machine distante.

Exemples :

- SSH disponible ;
- OS et architecture ;
- paquets installes ;
- valeurs `sysctl` ;
- presence de k3s ;
- version k3s ;
- etat systemd ;
- readiness du noeud ;
- etat des pods systeme.

### Planner

Convertit :

```text
DesiredState + ObservedState -> Plan
```

Le plan contient une liste ordonnee d'actions, avec les dependances, risques, verifications et rollbacks disponibles.

### Action

Chaque changement systeme est une action verifiable.

Contrat conceptuel :

```python
class Action:
    id: str
    description: str
    risk: str
    rollback_mode: str

    def precheck(self) -> None: ...
    def snapshot(self) -> object: ...
    def apply(self) -> None: ...
    def verify(self) -> bool: ...
    def rollback(self) -> None: ...
```

Exemples d'actions :

- `EnsurePackagePresent`
- `SetSysctlValue`
- `WriteRemoteFile`
- `InstallK3s`
- `UninstallK3s`
- `EnableSystemdService`
- `StartSystemdService`
- `WaitK3sNodeReady`
- `FetchKubeconfig`

### Runner

Execute le plan.

Boucle cible :

```text
for action in plan:
    action.precheck()
    snapshot = action.snapshot()
    journal.record_started(action, snapshot)

    action.apply()

    if not action.verify():
        journal.record_failed(action)
        rollback_previous_actions()
        stop

    journal.record_committed(action)
```

### Journal

Le journal conserve l'etat de chaque execution.

Il doit contenir :

- `run_id` ;
- manifeste utilise ;
- machine cible ;
- plan calcule ;
- action demarree ;
- snapshot avant action ;
- statut final ;
- rollback disponible ;
- erreurs et sorties importantes.

Exemple :

```json
{
  "run_id": "2026-04-28T14:22:01Z",
  "host": "prod-1",
  "actions": [
    {
      "id": "write-k3s-config",
      "status": "committed",
      "rollback": "restore previous config backup"
    },
    {
      "id": "install-k3s",
      "status": "failed_verify",
      "rollback": "run /usr/local/bin/k3s-uninstall.sh"
    }
  ]
}
```

## Rollback

Le rollback doit etre explicite et classe par niveau de garantie.

Modes :

- `reversible` : retour direct a l'etat precedent, par exemple restaurer un fichier sauvegarde ;
- `compensating` : action inverse raisonnable, par exemple desinstaller k3s apres une installation ;
- `none` : pas de rollback automatique fiable.

Risques :

- `low` : fichier de configuration, service systemd ;
- `medium` : installation ou desinstallation de paquets ;
- `high` : upgrade k3s, donnees cluster, reseau ;
- `destructive` : suppression de donnees.

Les actions irreversibles ou destructives doivent demander une confirmation explicite avant execution, sauf option forcee.

### Limites du rollback automatique

Certaines actions ne peuvent pas etre annulees de facon fiable :

- `WaitK3sNodeReady` : attente pure, pas d'etat a restaurer (`none`) ;
- `UninstallK3s` : la reinstallation automatique n'est pas fiable car les donnees cluster et la configuration initiale ne sont pas preservees (`none`) ;
- `EnsurePackagePresent` : si le paquet etait deja present avant l'apply, le rollback ne le supprime pas pour eviter de casser l'existant.

Les modes `reversible` (restauration de fichier ou de valeur sysctl) et `compensating` (desinstallation de paquet ou de k3s) sont fiables dans les conditions normales.

### Risques d'upgrade k3s

L'upgrade k3s (`k3s.upgrade`) porte un risque eleve pour les raisons suivantes :

- Le noeud redemarrera automatiquement le service k3s et peut interrompre les charges de travail en cours.
- En cluster multi-noeuds, upgrader un seul noeud peut creer une incompatibilite de version avec le plan de controle.
- Le rollback (`compensating`) reinstalle l'ancienne version mais ne garantit pas la restauration de l'etat etcd si des migrations de schema ont eu lieu.
- En cas d'echec de verification post-upgrade, le rollback peut lui-meme echouer si le script d'installation ne trouve plus la version anterieure dans le canal stable.

Recommandation : toujours tester un upgrade sur un noeud de staging avant production, et utiliser `pilot plan --dry-run` pour verifier les actions prevues.

## Manifeste d'installation

```yaml
apiVersion: cluster-pilot.dev/v1alpha1
kind: Machine
metadata:
  name: prod-1
  labels:
    env: production
    role: k3s-server

spec:
  connectionRef: prod-1

  system:
    packages:
      present:
        - curl
        - iptables
        - ca-certificates

    sysctl:
      net.ipv4.ip_forward: "1"
      net.bridge.bridge-nf-call-iptables: "1"

  k3s:
    state: present
    role: server
    version: v1.30.5+k3s1

    install:
      channel: stable
      method: official-script

    config:
      cluster-init: true
      write-kubeconfig-mode: "0644"
      disable:
        - traefik
        - servicelb

    service:
      enabled: true
      running: true

  health:
    require:
      - ssh.available
      - system.os.supported
      - system.disk.available
      - system.memory.available
      - systemd.k3s.running
      - k3s.version.matches
      - k3s.node.ready
      - k3s.systemPods.healthy

    thresholds:
      diskFreePercent: 15
      memoryFreeMiB: 512

  execution:
    mode: transactional

    plan:
      showDiff: true
      includeNoop: false

    verify:
      afterEachAction: true
      timeoutSeconds: 120

    rollback:
      enabled: true
      on:
        - applyFailure
        - verifyFailure

      requireConfirmFor:
        - destructive
        - irreversible

      strategy: reverse-applied-actions

    journal:
      location: local
      path: .pilot/runs
      keep: 20
```

## Manifeste de desinstallation

```yaml
apiVersion: cluster-pilot.dev/v1alpha1
kind: Machine
metadata:
  name: prod-1

spec:
  connectionRef: prod-1

  k3s:
    state: absent

    uninstall:
      removeData: false
      removeKubeconfig: true

  health:
    require:
      - ssh.available
      - k3s.absent
      - systemd.k3s.absent

  execution:
    mode: transactional
    rollback:
      enabled: true
      on:
        - verifyFailure
```

## Inventaire prive

Les manifestes versionnes ne doivent pas contenir d'informations de connexion
reelles. Ils referencent une entree d'inventaire via `spec.connectionRef`.

Exemple versionnable :

```yaml
apiVersion: cluster-pilot.dev/v1alpha1
kind: Machine
metadata:
  name: prod-1

spec:
  connectionRef: prod-1

  k3s:
    state: present
    role: server
```

Inventaire local non versionne :

```yaml
connections:
  prod-1:
    type: ssh
    host: 192.0.2.10
    user: root
    port: 22
    identityFile: ~/.ssh/id_ed25519
```

Convention :

- `examples/inventory.example.yaml` est public et documente la forme attendue ;
- `inventory.local.yaml` est ignore par Git et contient les vraies connexions ;
- `*.local.yaml` est ignore par Git pour les variantes personnelles.

Commande cible :

```bash
pilot inspect examples/single-server.yaml --inventory inventory.local.yaml
```

## Exemple de plan

Sortie cible :

```text
Plan: prod-1

1. Ensure package curl is present
2. Ensure package iptables is present
3. Set sysctl net.ipv4.ip_forward = 1
4. Write /etc/rancher/k3s/config.yaml
5. Install k3s v1.30.5+k3s1
6. Enable k3s service
7. Start k3s service
8. Wait for node Ready
9. Fetch kubeconfig

Risk: medium
Rollback available: partial
```

## Plan

Le phasage du projet est suivi dans [Plan](plan.md).
