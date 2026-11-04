#!/bin/sh
# Build noisycompany + luci-app-noisycompany .ipk/.apk from this checkout, inside the
# official OpenWrt SDK container (used by CI):
#   docker run --rm -v "$PWD:/src:ro" -v "$PWD/out:/out" openwrt/sdk:<tag> sh /src/deploy/openwrt/ci-build.sh
# The package Makefile fetches the release tag; here the source tree override points it
# at the checkout instead, so a pull request builds what it changes.
set -eu
SDK=${SDK:-/builder}
cd "$SDK"
cp -r /src/deploy/openwrt/package/noisycompany /src/deploy/openwrt/package/luci-app-noisycompany package/
# The override checks the tree out in place: give it a writable clone of the checkout.
git config --global --add safe.directory '*'
git clone -q /src /tmp/nc-src
ln -s /tmp/nc-src/.git package/noisycompany/git-src
./scripts/feeds update base luci >/dev/null
./scripts/feeds install luci-base >/dev/null
make defconfig >/dev/null
echo "CONFIG_SRC_TREE_OVERRIDE=y" >> .config
make package/noisycompany/compile package/luci-app-noisycompany/compile V=s -j"$(nproc)" >build.log 2>&1 \
  || { tail -60 build.log; exit 1; }
mkdir -p /out
find bin/packages -name 'noisycompany*' -o -name 'luci-app-noisycompany*' | while read -r f; do
  cp "$f" /out/; echo "built $(basename "$f")"; done
ls /out | grep -q '^noisycompany' && ls /out | grep -q '^luci-app-noisycompany'
