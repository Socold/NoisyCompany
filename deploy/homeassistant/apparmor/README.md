# AppArmor profile (draft)

`apparmor.txt` confines the add-on to what it uses: network sockets, `/data`, interface
counters and the image's Python. It is parsed by `apparmor_parser` in CI, but it has not
run on a Home Assistant Supervisor yet, so it is not active.

To try it:

1. Copy `apparmor.txt` next to `config.yaml` in a local copy of the add-on, rebuild.
2. Start the add-on, switch on `privacy_report`, leave it a day.
3. On the host: `journalctl -k | grep -i 'apparmor="DENIED".*noisycompany'` must be empty,
   and `noisycompany health` (add-on watchdog) must stay green.
4. If both hold, move the file up one folder in a pull request with the log excerpt.
