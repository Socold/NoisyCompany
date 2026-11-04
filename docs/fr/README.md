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
(`noisycompany packs install <nom>`). Le reste est
listé « planned » : voir la [feuille de route](../ROADMAP.md).

Voir aussi : [état de l'art](../STATE_OF_THE_ART.md), [opportunités](../OPPORTUNITIES.md).
