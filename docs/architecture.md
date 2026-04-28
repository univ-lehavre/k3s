# k3sctl - Architecture et phasage

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

## Organisation du depot

Le depot est un monorepo `uv workspace`, avec des paquets separes par responsabilite.

```text
k3s/
  pyproject.toml
  uv.lock
  README.md

  packages/
    k3splan/
      src/k3splan/
        desired.py
        observed.py
        planner.py
        actions/
        runner.py
        journal.py
      tests/

    k3sremote/
      src/k3sremote/
        ssh.py
        systemd.py
        files.py
        packages.py
      tests/

    k3scli/
      src/k3scli/
        app.py
        commands/
      tests/

  examples/
    single-server.yaml
    uninstall.yaml
    inventory.example.yaml

  docs/
    architecture.md
    manifest.md
```

Responsabilites :

- `k3splan` contient le moteur declaratif pur : manifestes, etat observe, planification, actions, runner, journal ;
- `k3sremote` contient les adaptateurs systeme : SSH, systemd, fichiers distants, commandes k3s ;
- `k3scli` contient l'interface utilisateur : commandes Typer, affichage Rich, options CLI.

Regle de dependance :

```text
k3scli -> k3splan + k3sremote
k3sremote -> k3splan si besoin de types communs
k3splan -> aucune dependance vers CLI ou SSH
```

Le coeur doit rester testable sans machine distante.

## CLI cible

Le binaire s'appelle `k3sctl`.

Commandes initiales :

```bash
k3sctl inspect examples/single-server.yaml --inventory inventory.local.yaml
k3sctl plan examples/single-server.yaml
k3sctl apply examples/single-server.yaml
k3sctl verify examples/single-server.yaml
k3sctl rollback --run-id <run-id>
k3sctl journal
```

Commandes utiles ensuite :

```bash
k3sctl apply examples/single-server.yaml --inventory inventory.local.yaml --step
k3sctl apply examples/single-server.yaml --inventory inventory.local.yaml --from action.install-k3s
k3sctl drift examples/single-server.yaml --inventory inventory.local.yaml
k3sctl doctor examples/single-server.yaml --inventory inventory.local.yaml
```

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

## Manifeste d'installation

```yaml
apiVersion: k3sctl.dev/v1alpha1
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
      path: .k3sctl/runs
      keep: 20
```

## Manifeste de desinstallation

```yaml
apiVersion: k3sctl.dev/v1alpha1
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
apiVersion: k3sctl.dev/v1alpha1
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
k3sctl inspect examples/single-server.yaml --inventory inventory.local.yaml
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

## Phasage

Statuts :

- ✅ `done` : realise et verifie ;
- 🟡 `partial` : premiere version disponible, mais contrat incomplet ;
- ⬜ `todo` : non demarre.

Etat actuel :

```text
✅ Phase 0  Cadrage du socle
✅ Phase 1  Manifeste et validation
✅ Phase 2  Inspection lecture seule
🟡 Phase 3  Planification
⬜ Phase 4  Actions verifiables
⬜ Phase 5  Runner et journal
⬜ Phase 6  k3s present
⬜ Phase 7  k3s absent
⬜ Phase 8  Health et drift
🟡 Phase 9  Durcissement
```

### Phase 0 - Cadrage du socle

Statut : ✅ `done`

Objectif : obtenir un depot Python propre avec workspace `uv`.

Actions :

- ✅ creer le `pyproject.toml` racine
- ✅ configurer le workspace `uv`
- ✅ creer les paquets `k3splan`, `k3sremote`, `k3scli`
- ✅ configurer `pytest`, `ruff`, `mypy`
- ✅ exposer le script `k3sctl`
- ✅ ajouter `pre-commit` et les hooks Git
- ✅ ajouter Commitizen pour version, bump et changelog

Definition of done :

- ✅ `uv run k3sctl --help` fonctionne
- ✅ `uv run pytest` fonctionne
- ✅ `uv run ruff check .` fonctionne
- ✅ `uv run mypy packages` fonctionne
- ✅ `uv run pre-commit run --all-files` fonctionne
- ✅ `uv run pre-commit run --hook-stage pre-push --all-files` fonctionne

### Phase 1 - Manifeste et validation

Statut : ✅ `done`

Objectif : charger et valider un manifeste `Machine`.

Actions :

- ✅ definir les modeles Pydantic
- ✅ implementer le chargement YAML
- ✅ ajouter `examples/single-server.yaml`
- ✅ ajouter `examples/uninstall.yaml`
- ✅ ajouter `examples/inventory.example.yaml`
- ✅ ajouter la commande `k3sctl validate <manifest>`
- ✅ accepter `spec.connectionRef` pour eviter les connexions reelles dans les manifests publics
- ✅ ajouter `--inventory` pour valider la resolution de connexion
- ✅ ignorer `inventory.local.yaml` et `*.local.yaml`

Definition of done :

- ✅ un manifeste valide est accepte
- ✅ les erreurs de schema sont lisibles
- ✅ les tests couvrent les champs obligatoires et les valeurs invalides
- ✅ un manifeste avec `connectionRef` peut etre resolu via inventaire
- ✅ un manifeste sans source de connexion est refuse

Livrables :

- `packages/k3splan/src/k3splan/manifest.py`
- `examples/single-server.yaml`
- `examples/uninstall.yaml`
- `examples/inventory.example.yaml`
- `docs/manifest.md`

### Phase 2 - Inspection lecture seule

Statut : ✅ `done`

Objectif : observer une machine distante sans modifier son etat.

Actions :

- ✅ implementer une interface `RemoteExecutor`
- ✅ ajouter un adaptateur SSH
- ✅ collecter OS, distribution, version, architecture, systemd, k3s, disque, memoire
- ✅ collecter l'etat APT : disponibilite, fraicheur des listes et paquets upgradables
- ✅ ajouter la commande `k3sctl inspect <manifest>`

Definition of done :

- ✅ l'inspection fonctionne sur une machine accessible en SSH
- ✅ l'etat observe est serialisable en JSON
- ✅ les tests unitaires utilisent un faux executor

Regle APT :

- ✅ `apt system up to date` vaut `yes` seulement si les listes APT sont recentes et si aucun paquet n'est upgradable

Ameliorations futures :

- ⬜ ajouter une sortie JSON pour automatisation

### Phase 3 - Planification

Statut : 🟡 `partial`

Objectif : produire un plan d'actions sans appliquer.

Actions :

- 🟡 definir les classes `ObservedState`, `Plan` et `ActionSpec`
- 🟡 implementer le diff `desired + observed -> plan`
- ✅ ajouter la commande `k3sctl plan <manifest>`
- ✅ afficher le plan avec `rich`

Definition of done :

- ✅ une machine sans k3s produit un plan d'installation avec etat observe
- ⬜ une machine conforme produit un plan vide ou des no-op masques
- ⬜ une machine avec derive de version produit une action d'upgrade ou un avertissement

Reste a faire :

- ✅ introduire `ObservedState`
- ✅ brancher `plan` sur l'inspection reelle ou un fake d'etat observe
- ⬜ distinguer actions reelles et no-op
- ⬜ tester les derives de version, config et service

### Phase 4 - Actions verifiables minimales

Statut : ⬜ `todo`

Objectif : executer des actions simples et les verifier.

Actions :

- ⬜ implementer `EnsurePackagePresent`
- ⬜ implementer `WriteRemoteFile` avec backup
- ⬜ implementer `SetSysctlValue`
- ⬜ definir `precheck`, `snapshot`, `apply`, `verify`, `rollback`

Definition of done :

- ⬜ chaque action peut etre testee avec un executor fake
- ⬜ chaque action expose son mode de rollback
- ⬜ une verification echouee est detectee

### Phase 5 - Runner transactionnel et journal

Statut : ⬜ `todo`

Objectif : executer un plan avec journalisation et rollback.

Actions :

- ⬜ implementer le `Runner`
- ⬜ ecrire un journal local par `run_id`
- ⬜ enregistrer snapshots, statuts et erreurs
- ⬜ executer le rollback en ordre inverse
- ⬜ ajouter `k3sctl apply <manifest>`

Definition of done :

- ⬜ une action echouee stoppe l'execution
- ⬜ les actions deja appliquees sont rollbackees si possible
- ⬜ `k3sctl journal` liste les executions
- ⬜ `k3sctl rollback --run-id <run-id>` fonctionne pour les actions rollbackables

### Phase 6 - k3s present

Statut : ⬜ `todo`

Objectif : installer et demarrer k3s declarativement.

Actions :

- ⬜ implementer `InstallK3s`
- ⬜ implementer `WriteK3sConfig`
- ⬜ implementer `EnableSystemdService`
- ⬜ implementer `StartSystemdService`
- ⬜ implementer `WaitK3sNodeReady`
- ⬜ implementer `FetchKubeconfig`

Definition of done :

- ⬜ `k3sctl plan` annonce les actions d'installation
- ⬜ `k3sctl apply` installe k3s sur une machine de test
- ⬜ `k3sctl verify` confirme service running, version attendue et node ready

### Phase 7 - k3s absent

Statut : ⬜ `todo`

Objectif : desinstaller k3s proprement.

Actions :

- ⬜ implementer `UninstallK3s`
- ⬜ gerer `removeData`
- ⬜ gerer `removeKubeconfig`
- ⬜ verifier absence service, binaire et configuration selon options

Definition of done :

- ⬜ `state: absent` produit un plan de desinstallation
- ⬜ la desinstallation est bloquee ou confirmee si elle est destructive
- ⬜ la verification confirme l'absence attendue

### Phase 8 - Health et drift

Statut : ⬜ `todo`

Objectif : rendre l'outil utile au quotidien.

Actions :

- ⬜ ajouter `k3sctl doctor <manifest>`
- ⬜ ajouter `k3sctl drift <manifest>`
- ⬜ structurer les checks de sante
- ⬜ afficher un verdict clair : `healthy`, `degraded`, `unhealthy`

Definition of done :

- ⬜ le rapport distingue sante systeme, sante k3s et derive declarative
- ⬜ les seuils du manifeste sont appliques
- ⬜ le CLI propose la prochaine action pertinente

### Phase 9 - Durcissement

Statut : 🟡 `partial`

Objectif : rendre le projet robuste avant usage reel.

Actions :

- ⬜ ajouter tests d'integration sur VM ou container systemd si possible
- 🟡 documenter les limites de rollback
- ⬜ documenter les risques d'upgrade k3s
- ⬜ ajouter mode `--dry-run` strict
- ⬜ ajouter confirmations pour actions destructives
- ⬜ stabiliser le schema `v1alpha1`
- ✅ documenter la separation manifeste public / inventaire prive
- ✅ ajouter hooks qualite locaux
- ✅ ajouter workflow de release local

Definition of done :

- 🟡 la documentation couvre installation, desinstallation, rollback et limites
- 🟡 les commandes critiques ont des tests
- ⬜ les erreurs CLI sont comprehensibles et actionnables
