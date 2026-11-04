# Home-server app templates

Same image and hardening everywhere: host network (netwatch must see your traffic),
read-only root, no capability, 96 MB of memory, eco preset, state in one directory
owned by uid 10001. No port is published: the dashboard and metrics stay on
`127.0.0.1` of the server.

| Platform | File | How |
|---|---|---|
| Umbrel | `umbrel/noisycompany/` | Community app store layout (add the folder to your store repo) |
| CasaOS / ZimaOS | `casaos/docker-compose.yml` | App Store > Custom install > Import |
| TrueNAS SCALE 24.10+ | `truenas/compose.yaml` | Apps > Install via YAML (set your pool) |
| Unraid | `unraid/noisycompany.xml` | Copy to `templates-user/`, then Add Container |
| Pi-hole / AdGuard Home box | `../pihole/` | Next to the resolver, with the study |

These templates follow each platform's documented format but were not installed on
every platform before release: report problems in an issue.
