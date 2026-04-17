include upstream.sh
export

cf_source_dir := firefox-src
ff_source_tarball := firefox-$(version).source.tar.xz

_ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
$(eval $(_ARGS):;@:)

.PHONY: help fetch setup setup-minimal clean distclean build package \
        patch unpatch dir run mozbootstrap bootstrap extension set-target \
        package-linux package-macos package-windows

help:
	@echo "Cloakfox Build System"
	@echo ""
	@echo "  make fetch         Download Firefox source tarball"
	@echo "  make setup-minimal Extract source and copy additions (for CI)"
	@echo "  make setup         setup-minimal + git init (for development)"
	@echo "  make mozbootstrap  Bootstrap mach build environment"
	@echo "  make dir           Apply patches and prepare source"
	@echo "  make extension     Build Cloakfox Shield extension"
	@echo "  make build         Compile Firefox"
	@echo "  make set-target    Update mozconfig for BUILD_TARGET"
	@echo "  make run           Launch the built browser"
	@echo "  make clean         Remove build artifacts"
	@echo "  make distclean     Remove everything including source"
	@echo ""

fetch:
	scripts/fetch-firefox.sh $(version)

setup-minimal:
	if [ ! -f $(ff_source_tarball) ]; then \
		make fetch; \
	fi
	rm -rf $(cf_source_dir)
	mkdir -p $(cf_source_dir)
	tar -xJf $(ff_source_tarball) -C $(cf_source_dir) --strip-components=1
	cd $(cf_source_dir) && bash ../scripts/copy-additions.sh $(version) $(release)

setup: setup-minimal
	cd $(cf_source_dir) && \
		git init -b main && \
		git add -f -A && \
		git commit -m "Initial commit" && \
		git tag -a unpatched -m "Initial commit"

mozbootstrap:
	cd $(cf_source_dir) && MOZBUILD_STATE_PATH=$$HOME/.mozbuild ./mach --no-interactive bootstrap --application-choice=browser

bootstrap: dir
	make mozbootstrap

dir:
	@if [ ! -d $(cf_source_dir) ]; then \
		make setup; \
	fi
	python3 scripts/patch.py $(version) $(release)
	python3 scripts/fix-mach-logging.py $(cf_source_dir)
	touch $(cf_source_dir)/_READY

set-target:
	python3 scripts/patch.py $(version) $(release) --mozconfig-only

extension:
	cd additions/browser/extensions/cloakfox-shield && npm ci && npm run build

build:
	@if [ ! -f $(cf_source_dir)/_READY ]; then \
		make dir; \
	fi
	cd $(cf_source_dir) && ./mach build

run:
	cd $(cf_source_dir) && ./mach run

package-linux:
	python3 scripts/package.py linux --version $(version) --release $(release) --arch $(_ARGS)

package-macos:
	python3 scripts/package.py macos --version $(version) --release $(release) --arch $(_ARGS)

package-windows:
	python3 scripts/package.py windows --version $(version) --release $(release) --arch $(_ARGS)

generate-assets-car:
	bash scripts/generate-assets-car.sh

clean:
	rm -rf $(cf_source_dir)/obj-*
	rm -rf additions/browser/extensions/cloakfox-shield/dist
	rm -f *.dmg

distclean: clean
	rm -rf $(cf_source_dir)
	rm -rf additions/browser/extensions/cloakfox-shield/node_modules
	rm -f $(ff_source_tarball)

patch:
	cd $(cf_source_dir) && patch -p1 -i ../$(_ARGS)

unpatch:
	cd $(cf_source_dir) && patch -p1 -R -i ../$(_ARGS)
