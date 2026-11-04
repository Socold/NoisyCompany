# NoisyCompany (résumé en français)

noisycompany génère en arrière-plan un trafic DNS et web **plausible, léger et poli**, pour
diluer ce qu'un observateur réseau (FAI, Wi-Fi public, résolveur DNS) peut déduire de
vos centres d'intérêt.

## Ce que ça fait, ce que ça ne fait pas

- **Utile contre** : le profilage par le FAI, le résolveur DNS, le Wi-Fi public, les
  courtiers de données qui achètent ces données.
- **Inutile contre** : la publicité ciblée par cookies, pixels et empreinte du navigateur
  (là où se fait l'essentiel du ciblage) et la reconnaissance entre sites. Pour cela :
  uBlock Origin, DNS chiffré, navigateur anti-empreinte. NoisyCompany est un complément.

Détails : [modèle de menace](../THREAT_MODEL.md).

## Légèreté

| Préréglage | Données/jour | Débit moyen | Énergie réseau/mois |
|---|---|---|---|
| eco | ~2 Mo | ~0,3 kbit/s | 0,3 à 4 Wh |
| balanced (défaut) | ~15 Mo | ~2 kbit/s | 2 à 27 Wh |
| max | ~60 Mo | ~9 kbit/s | 9 à 108 Wh |

Plafond quotidien strict, pages coupées à 192 Ko, HTML seul, pause automatique quand
vous utilisez votre connexion (Linux), silence la nuit. `noisycompany estimate` donne ces
chiffres avant tout lancement. Détails : [impact](../IMPACT.md).

## Démarrer

```bash
pip install .
noisycompany estimate
noisycompany run --dry-run --once
noisycompany run
```

## Interrupteurs on/off

Chaque élément de la feuille de route a un interrupteur, désactivé par défaut :
`noisycompany features` (liste), `noisycompany features on <id>`, ou les boutons du
tableau de bord local (`noisycompany features on dashboard`, puis http://127.0.0.1:9788).
Disponibles : dérive des personas, pack de personas français, garde connexion limitée,
DNS sur HTTPS, métriques Prometheus, journal étiqueté pour tester un SOC, rapport de
confidentialité (`noisycompany privacy` : bloqueur, DNS chiffré, anti-empreinte, GPC,
IPv6, cohérence du bruit, score sur 100, rien n'est envoyé) et packs de personas relus
(`noisycompany packs install <nom>`), profils métier pour labos SOC (`business_profiles` :
bureau, équipe de dev, commerce) et arbres de requêtes réalistes (`request_trees`, CSS/JS
du même site une seule fois, environ +60 % de données). Réalisme : packs allemand,
espagnol et italien, DNS qui suit les pages lues (`dns_coherence`), rythme de la semaine
et des congés (`weekly_rhythm`), rafales DNS des domaines tiers d'une page sans
téléchargement ni traqueurs (`third_party_bursts`).

Boîtiers : add-on Home Assistant, docker-compose, installateur Raspberry Pi, service
OpenWrt, image multi-architecture et `noisycompany health`. Bruit collectif : des foyers
partagent un code court (`noisycompany collective`) et font tourner les mêmes leurres au
même moment, sans serveur et sans pouvoir ajouter de domaine. Étude de détectabilité :
`noisycompany study` mesure (AUC) si un observateur peut séparer le bruit de votre trafic
réel, voir [STUDY.md](../STUDY.md).

Extension Firefox ([companion/](../../companion/README.md)) : les mêmes visites rares, faites
par votre vrai navigateur, donc avec la même empreinte réseau. Désactivée par défaut, mode
léger sans cookie ou mode onglet caché dans un conteneur dédié. Le reste est
listé « planned » : voir la [feuille de route](../ROADMAP.md).

## Sécurité et confidentialité

Audit de novembre 2026 ([rapport](../SECURITY_AUDIT_2026-11.md)) : 12 points corrigés en
2.0.1. Les plus importants :
- aucune redirection ni adresse du réseau local (box, NAS) n'est suivie ;
- la décompression est plafonnée ;
- les fichiers d'état sont privés ;
- l'en-tête de langue correspond à la persona.

Aucune télémétrie, aucun compte, aucun serveur. Ce qui est envoyé, stocké et lu est listé
dans [PRIVACY.md](../PRIVACY.md).

## Prochaines évolutions

Durcissement et réalisme sont faits (2.1, 2.2). Reste de ces lots : profil AppArmor, publication PyPI, rythme par persona, tailles de paquets dans l'étude. 2.3 faite aussi : extension pour Chrome, Brave et Edge
(mode léger), choix des langues, pilotage par l'interrupteur du démon, conteneur par
défaut sur avertissement ; la signature addons.mozilla.org attend les clés. 2.4 faite : boîtier Pi-hole / AdGuard
Home avec l'étude (`deploy/pihole/`), modèles Umbrel, CasaOS, TrueNAS et Unraid
(`deploy/apps/`), paquet OpenWrt avec page LuCI, tableau Grafana, tableau de bord en
français (langue du navigateur ou `?lang=fr`) et audit d'accessibilité. Ensuite : codes de collectif en QR, banc d'essai public de détectabilité,
mesure réelle de l'énergie. Détail : [ROADMAP.md](../ROADMAP.md#next-evolutions).

Voir aussi : [état de l'art](../STATE_OF_THE_ART.md), [opportunités](../OPPORTUNITIES.md),
[architecture](../ARCHITECTURE.md), [étude](../STUDY.md).
