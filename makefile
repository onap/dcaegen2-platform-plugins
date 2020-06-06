none:
	@echo make verify-versions

verify-versions:
	@echo check pom.xml against setup.py and types.yaml files
	@for i in */pom.xml; do \
		p=$$(dirname $$i); \
		echo Working on $$i; \
		v=$$(grep "<version>" $$i | sed 2q | tail -n 1 | sed -e 's!</\?version>!!g' -e 's/-SNAPSHOT//' -e 's/[[:space:]]//g'); \
		if grep 'version[[:space:]]*=[[:space:]]*["'"']$$v['"'"]' $$p/setup.py > /dev/null; then \
			echo "$$i version $$v verified in $$p/setup.py"; \
		else \
			grep -n "<version>" $$i /dev/null | sed 2q | tail -n 1; \
			grep -n "version[[:space:]]*=" $$p/setup.py /dev/null; \
			echo "$$i version $$v not found in $$p/setup.py. Instead found the above version."; \
			exit 1 ; \
		fi; \
		if [ -f "$$p"/*types.yaml ]; then \
			if grep "package_version:[[:space:]]*$$v" "$$p"/*types.yaml > /dev/null 2>&1; then \
				echo "$$i version $$v verified in" "$$p"/*types.yaml; \
			else \
				grep -n "<version>" $$i /dev/null | sed 2q | tail -n 1; \
				grep -n "package_version:" "$$p"/*types.yaml /dev/null; \
				exit 1 ; \
			fi; \
		else \
			echo "No types file found in $$p"; \
		fi; \
		echo; \
	done
	@pomv=$$(grep "<version>" pom.xml | sed 2q | tail -n 1 | sed -e 's!</\?version>!!g' -e 's/[[:space:]]//g'); \
	for i in */pom.xml; do \
		v=$$(grep "<version>" $$i | sed 1q | sed -e 's!</\?version>!!g' -e 's/[[:space:]]//g'); \
		if [ "$$pomv" = "$$v" ]; then \
			echo "pom.xml version $$pomv verified in $$i"; \
		else \
			grep -n "<version>" $$i /dev/null | sed 1q; \
			echo "pom.xml version $$pomv not found in $$i. Instead found $$v"; \
			exit 1 ; \
		fi; \
	done
