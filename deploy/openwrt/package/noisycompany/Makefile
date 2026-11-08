# OpenWrt package (build with the SDK: copy this folder to package/, then
# `make package/noisycompany/compile`). Pure Python, architecture independent.
include $(TOPDIR)/rules.mk

PKG_NAME:=noisycompany
PKG_VERSION:=2.1.0
PKG_RELEASE:=1
PKG_LICENSE:=GPL-3.0-or-later
PKG_MAINTAINER:=NoisyCompany contributors

PKG_SOURCE_PROTO:=git
PKG_SOURCE_URL:=https://github.com/Socold/NoisyCompany.git
PKG_SOURCE_VERSION:=v$(PKG_VERSION)
PKG_MIRROR_HASH:=skip

include $(INCLUDE_DIR)/package.mk

define Package/noisycompany
  SECTION:=net
  CATEGORY:=Network
  TITLE:=Light network noise with coherent decoy personas
  URL:=https://github.com/Socold/NoisyCompany
  DEPENDS:=+python3-light +python3-urllib +python3-logging +python3-email \
           +python3-openssl +python3-codecs
  PKGARCH:=all
endef

define Package/noisycompany/description
  Rare, plausible DNS and web activity that dilutes what the ISP sees about the
  household. Eco preset, a few MB per day, state in RAM (spares the flash).
endef

define Package/noisycompany/conffiles
/etc/config/noisycompany
endef

define Build/Compile
endef

define Package/noisycompany/install
	$(INSTALL_DIR) $(1)/usr/lib/noisycompany
	$(CP) $(PKG_BUILD_DIR)/src/noisycompany $(1)/usr/lib/noisycompany/
	$(INSTALL_DIR) $(1)/etc/init.d $(1)/etc/config
	$(INSTALL_BIN) ./files/noisycompany.init $(1)/etc/init.d/noisycompany
	$(INSTALL_CONF) ./files/noisycompany.config $(1)/etc/config/noisycompany
endef

$(eval $(call BuildPackage,noisycompany))
