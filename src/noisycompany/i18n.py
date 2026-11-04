"""CLI messages in French when the locale asks for it (stdlib only, no gettext files).

Language: NOISYCOMPANY_LANG, then LC_ALL, LC_MESSAGES, LANG. Only "fr" is translated;
anything else stays in English. Tables, JSON and reports keep their English field names
so scripts that parse them do not break.
"""

from __future__ import annotations

import os

FR = {
    "(used when the persona_marketplace switch is on)":
        "(utilisés quand l'interrupteur persona_marketplace est activé)",
    "QR code written to {p}": "QR code écrit dans {p}",
    "SOC test scenarios: labelled benign traffic, offline":
        "scénarios de test SOC : trafic bénin étiqueté, hors ligne",
    "TOML config file": "fichier de configuration TOML",
    "bandwidth and energy estimate": "estimation de bande passante et d'énergie",
    "check: allow files without [meta]": "check : accepter les fichiers sans [meta]",
    "companion files up to date": "fichiers du compagnon à jour",
    "config error: {e}": "erreur de configuration : {e}",
    "create/rotate: code valid this many days (0 = no expiry)":
        "create/rotate : code valable ce nombre de jours (0 = sans expiration)",
    "create: also join it": "create : le rejoindre aussi",
    "create: also print a QR code": "create : afficher aussi un QR code",
    "create: collective name": "create : nom du collectif",
    "create: comma-separated personas (default: enabled)":
        "create : personas séparées par des virgules (défaut : celles activées)",
    "drop trace lines matching a noise event (same second + host)":
        "retirer de la trace les lignes d'un événement de bruit (même seconde + hôte)",
    "exit 0 if the daemon is alive": "code de sortie 0 si le démon est vivant",
    "fail if files are stale": "échouer si les fichiers sont périmés",
    "generate noise": "générer du bruit",
    "generate the browser companion's personas/manifest":
        "générer les personas et le manifeste du compagnon navigateur",
    "grid carbon intensity gCO2e/kWh (default 50, ~France; EU ~250)":
        "intensité carbone du réseau en gCO2e/kWh (défaut 50, ~France ; UE ~250)",
    "health file disabled (switch appliance_packages off)":
        "fichier de santé désactivé (interrupteur appliance_packages coupé)",
    "healthy: last heartbeat {s:.0f} s ago":
        "en bonne santé : dernier signe de vie il y a {s:.0f} s",
    "how separable is the noise?": "le bruit est-il facile à séparer ?",
    "installed {n}": "{n} installé",
    "join: share code or file": "join : code de partage ou fichier",
    "labelled log (JSONL) from labelled_log": "journal étiqueté (JSONL) de labelled_log",
    "left the collective": "collectif quitté",
    "list enabled personas": "lister les personas activées",
    "list or switch features on/off": "lister ou activer/couper les fonctions",
    "local privacy report and score": "rapport de confidentialité local et score",
    "measure CPU time and RAPL energy of real sessions":
        "mesurer le temps CPU et l'énergie RAPL de vraies sessions",
    "no collective joined": "aucun collectif rejoint",
    "no health file yet": "pas encore de fichier de santé",
    "no network (CPU cost only)": "sans réseau (coût CPU seulement)",
    "no network, log intended actions": "sans réseau, journalise les actions prévues",
    "not available yet: {e}": "pas encore disponible : {e}",
    "offline separability benchmark on simulated days":
        "banc d'essai de séparabilité hors ligne sur des jours simulés",
    "persona packs: list, install, check": "packs de personas : lister, installer, vérifier",
    "qr/rotate/create: write the QR code to this SVG file":
        "qr/rotate/create : écrire le QR code dans ce fichier SVG",
    "real trace: CSV or JSONL, time + domain": "trace réelle : CSV ou JSONL, heure + domaine",
    "removed {n}": "{n} retiré",
    "run a single session then exit": "une seule session puis sortie",
    "run: labelled JSONL output": "run : sortie JSONL étiquetée",
    "run: scenario name or .toml file": "run : nom du scénario ou fichier .toml",
    "seconds since the last heartbeat (default 180)":
        "secondes depuis le dernier signe de vie (défaut 180)",
    "shared decoy personas across households": "personas leurres partagées entre foyers",
    "show effective config": "afficher la configuration effective",
    "show: print the share code": "show : afficher le code de partage",
    "stale: last heartbeat {s:.0f} s ago": "figé : dernier signe de vie il y a {s:.0f} s",
    "unknown feature {f!r}": "fonction inconnue {f!r}",
    "usage: noisycompany collective join <code|file>":
        "usage : noisycompany collective join <code|fichier>",
    "usage: noisycompany features on|off <id>": "usage : noisycompany features on|off <id>",
    "where salt, switches and stats.json live":
        "dossier du sel, des interrupteurs et de stats.json",
    "packet capture (pcap/pcapng): study TLS flows instead":
        "capture de paquets (pcap/pcapng) : étudier les flux TLS à la place",
    "study needs --human or --pcap": "study demande --human ou --pcap",
    "TLS flows, not DNS windows:": "Flux TLS, pas des fenêtres DNS :",
    "window width, seconds": "largeur de fenêtre, secondes",
    "{f}: {a} (applies at the next session)": "{f} : {a} (appliqué à la prochaine session)",
    "{n} is not installed": "{n} n'est pas installé",
    "{t} is not a directory": "{t} n'est pas un dossier",
}


def language(env: dict[str, str] | None = None) -> str:
    env = os.environ if env is None else env
    for key in ("NOISYCOMPANY_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = env.get(key, "")
        if value:
            return value.split("_")[0].split(".")[0].lower()
    return "en"


def _(msg: str) -> str:
    return FR.get(msg, msg) if language() == "fr" else msg
