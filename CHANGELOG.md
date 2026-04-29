# Changelog

Tous les changements notables de ce projet seront documentes ici.

Le format s'appuie sur les Conventional Commits et le changelog est genere par
Commitizen lors des bumps de version.

## v0.2.0 (2026-04-29)

### Feat

- scaffold k3s agent
- stream apply output in real time via on_output callback
- add --dry-run and high-risk confirmation to apply command
- add doctor and drift commands
- implement UninstallK3s action
- implement k3s install, service and kubeconfig actions
- transactional runner, journal and apply command
- inspect packages and sysctl declared in manifest
- add verifiable action contracts and drift detection
- support Cilium CNI via k3s HelmChart mechanism
- support named contexts in k3sctl
- plan from observed machine state
- enrich inspect health indicators
- inspect remote machine state
- support private connection inventories
- scaffold k3sctl workspace

### Fix

- strip trailing newline in WriteRemoteFile verify
