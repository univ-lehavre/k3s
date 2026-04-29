# Manifestes et inventaires

Les manifestes k3sp decrivent l'etat attendu d'une machine. Ils peuvent etre versionnes dans un depot public tant qu'ils ne contiennent pas d'informations de connexion reelles.

Les informations de connexion sont separees dans un inventaire local.

## Table des matieres

- [Principe](#principe)
- [Fichiers](#fichiers)
- [Validation](#validation)
- [Regle de schema](#regle-de-schema)
- [Manifest d'installation](#manifest-dinstallation)
- [Manifest de desinstallation](#manifest-de-desinstallation)
- [Inventaire](#inventaire)
- [Securite](#securite)

## Principe

Un manifeste public contient une reference :

```yaml
spec:
  connectionRef: prod-1
```

Un inventaire local contient la connexion effective :

```yaml
connections:
  prod-1:
    type: ssh
    host: 192.0.2.10
    user: root
    port: 22
    identityFile: ~/.ssh/id_ed25519
```

`192.0.2.10` est une adresse reservee a la documentation. Les vraies adresses
sont a placer dans `inventory.local.yaml`, qui est ignore par Git.

## Fichiers

Fichiers versionnes :

- `examples/single-server.yaml` : exemple d'installation ;
- `examples/uninstall.yaml` : exemple de desinstallation ;
- `examples/inventory.example.yaml` : forme attendue d'un inventaire.

Fichiers locaux ignores :

- `inventory.local.yaml` ;
- `*.local.yaml`.

## Validation

Valider uniquement le manifeste :

```bash
uv run k3sp validate examples/single-server.yaml
```

Valider le manifeste et la resolution de connexion :

```bash
uv run k3sp validate examples/single-server.yaml --inventory inventory.local.yaml
```

Pour les exemples publics :

```bash
uv run k3sp validate examples/single-server.yaml --inventory examples/inventory.example.yaml
```

## Regle de schema

`spec` doit definir exactement une source de connexion :

- soit `connectionRef` pour referencer un inventaire ;
- soit `connection` pour une connexion inline.

Pour un depot public, utiliser `connectionRef`.

Le champ `connection` reste possible pour des tests locaux ou des usages prives,
mais il ne doit pas etre utilise dans les exemples publics.

## Manifest d'installation

```yaml
apiVersion: k3s-pilot.dev/v1alpha1
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
      net.ipv4.ip_forward: '1'
      net.bridge.bridge-nf-call-iptables: '1'

  k3s:
    state: present
    role: server
    version: v1.30.5+k3s1

    install:
      channel: stable
      method: official-script

    config:
      cluster-init: true
      write-kubeconfig-mode: '0644'
      disable:
        - traefik
        - servicelb

    service:
      enabled: true
      running: true
```

## Manifest de desinstallation

```yaml
apiVersion: k3s-pilot.dev/v1alpha1
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
```

## Inventaire

```yaml
connections:
  prod-1:
    type: ssh
    host: 192.0.2.10
    user: root
    port: 22
    identityFile: ~/.ssh/id_ed25519
```

Champs de connexion :

- `type` : actuellement `ssh` ;
- `host` : adresse ou nom DNS de la machine ;
- `user` : utilisateur SSH ;
- `port` : port SSH, `22` par defaut ;
- `identityFile` : cle SSH optionnelle.

## Securite

Ne pas versionner :

- adresses IP privees ou noms DNS internes ;
- utilisateurs d'administration reels ;
- chemins de cles SSH personnels si sensibles ;
- tokens k3s ;
- kubeconfigs ;
- inventaires locaux.

Les futurs secrets doivent passer par des references explicites, par exemple
`secretRef`, plutot que par des valeurs inline dans le manifeste.
