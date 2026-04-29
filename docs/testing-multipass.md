# Tester cluster-pilot avec Multipass

Ce guide permet de tester `pilot` contre une vraie machine Ubuntu locale via Multipass.

## Prerequis

- [Multipass](https://multipass.run/) installe (`brew install multipass` sur macOS)
- `uv` et l'environnement Python du projet (`uv sync --all-packages --dev`)
- Une cle SSH locale (`~/.ssh/id_ed25519` ou equivalent)

## 1. Creer la VM

```bash
multipass launch 24.04 --name pilot-test --cpus 2 --memory 2G --disk 10G
```

Verifier qu'elle tourne :

```bash
multipass list
```

## 2. Autoriser votre cle SSH

Multipass utilise son propre mecanisme de cle. La facon la plus simple est d'injecter votre cle publique :

```bash
multipass exec pilot-test -- bash -c "
  mkdir -p ~/.ssh
  echo '$(cat ~/.ssh/id_ed25519.pub)' >> ~/.ssh/authorized_keys
  chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys
"
```

## 3. Recuperer l'adresse IP

```bash
multipass info pilot-test | grep IPv4
```

## 4. Creer l'inventaire local

Creer `inventory.local.yaml` a la racine du depot (ignore par Git) :

```yaml
connections:
  pilot-test:
    type: ssh
    host: <IP-de-la-vm>
    user: ubuntu
    port: 22
    identityFile: ~/.ssh/id_ed25519
```

Remplacer `<IP-de-la-vm>` par l'adresse obtenue a l'etape precedente.

## 5. Valider la configuration

```bash
uv run pilot validate examples/multipass-test.yaml --inventory inventory.local.yaml
```

## 6. Inspecter la machine

```bash
uv run pilot inspect examples/multipass-test.yaml --inventory inventory.local.yaml
```

## 7. Planifier

```bash
uv run pilot plan examples/multipass-test.yaml --inventory inventory.local.yaml
```

## 8. Appliquer

```bash
uv run pilot apply examples/multipass-test.yaml --inventory inventory.local.yaml
```

## 9. Verifier l'etat de sante

```bash
uv run pilot doctor examples/multipass-test.yaml --inventory inventory.local.yaml
```

## 10. Tester le rollback

Recuperer le `run_id` du dernier apply :

```bash
uv run pilot journal list
```

Puis lancer le rollback :

```bash
uv run pilot rollback examples/multipass-test.yaml \
  --inventory inventory.local.yaml \
  --run-id <run_id>
```

## Cycle test complet

```bash
# Snapshot avant apply
multipass snapshot pilot-test --name before-apply

# Apply
uv run pilot apply examples/multipass-test.yaml --inventory inventory.local.yaml

# Verifier
uv run pilot doctor examples/multipass-test.yaml --inventory inventory.local.yaml

# Restaurer si besoin
multipass restore pilot-test --snapshot before-apply
```

## Nettoyage

```bash
multipass delete pilot-test --purge
```
