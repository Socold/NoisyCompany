# LuCI page: Services > NoisyCompany. Build with the SDK next to the luci feed.
include $(TOPDIR)/rules.mk

LUCI_TITLE:=LuCI support for NoisyCompany
LUCI_DEPENDS:=+noisycompany +luci-base
LUCI_PKGARCH:=all
PKG_LICENSE:=GPL-3.0-or-later

include $(TOPDIR)/feeds/luci/luci.mk

# call BuildPackage - OpenWrt buildroot signature
