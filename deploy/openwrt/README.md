# OpenWrt

Two ways:

- **Package** (`package/`): `noisycompany` (pure Python, `PKGARCH:=all`, UCI config
  `/etc/config/noisycompany`, procd service as `nobody`, state in `/tmp`) and
  `luci-app-noisycompany` (Services > NoisyCompany: enable, preset, daily cap, active
  hours, languages, weekly rhythm). Build with the OpenWrt SDK:

  ```bash
  cp -r package/noisycompany package/luci-app-noisycompany <sdk>/package/
  cd <sdk> && ./scripts/feeds update -a && ./scripts/feeds install -a
  make package/noisycompany/compile package/luci-app-noisycompany/compile
  opkg install bin/packages/*/base/noisycompany_*.ipk bin/packages/*/base/luci-app-noisycompany_*.ipk
  ```

- **Manual** (`noisycompany.init`): copy the sources and the init script, see its header.

Needs about 10 MB of flash for Python (`python3-light` and a few modules). The service
stays off until enabled in LuCI or with `uci set noisycompany.main.enabled=1 && uci commit`.
The package files follow the SDK conventions but were not built on every target yet.
