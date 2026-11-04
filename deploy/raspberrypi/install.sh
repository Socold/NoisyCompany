#!/usr/bin/env bash
# NoisyCompany on a Raspberry Pi (or any Debian/Ubuntu box), as a user service.
# Usage: curl -fsSL <raw url>/deploy/raspberrypi/install.sh -o install.sh && less install.sh && bash install.sh
# Read it first: it installs pipx (apt), NoisyCompany for the current user, and a
# hardened systemd user unit that keeps running after logout (linger).
set -euo pipefail
REF="${NOISYCOMPANY_REF:-main}"
PRESET="${NOISYCOMPANY_PRESET:-eco}"

if [ "$(id -u)" -eq 0 ]; then
  echo "Run as a normal user (sudo is used only for apt and linger)." >&2; exit 1
fi
command -v pipx >/dev/null || { sudo apt-get update -q && sudo apt-get install -y -q pipx; }
pipx install --force "git+https://github.com/Socold/NoisyCompany@${REF}"
mkdir -p ~/.config/noisycompany ~/.config/systemd/user ~/.local/state/noisycompany
CFG=~/.config/noisycompany/noisycompany.toml
if [ ! -f "$CFG" ]; then
  ~/.local/bin/noisycompany config --print-default \
    | sed "s/^preset = \"balanced\"/preset = \"${PRESET}\"/" > "$CFG"
fi
~/.local/bin/noisycompany features on appliance_packages >/dev/null
curl -fsSL "https://raw.githubusercontent.com/Socold/NoisyCompany/${REF}/deploy/systemd/noisycompany.service" \
  | sed "s|ExecStart=%h/.local/bin/noisycompany run|ExecStart=%h/.local/bin/noisycompany run -c %h/.config/noisycompany/noisycompany.toml|" \
  > ~/.config/systemd/user/noisycompany.service
sudo loginctl enable-linger "$USER"
systemctl --user daemon-reload
systemctl --user enable --now noisycompany
~/.local/bin/noisycompany estimate -c "$CFG"
echo "Installed. Status: systemctl --user status noisycompany ; health: noisycompany health"
