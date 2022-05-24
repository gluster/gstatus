VERSION ?= "master"
PYTHON ?= python3
PROGNAME = gstatus

help:
	@echo "make help        - Show this help message"
	@echo "make gen-version - Generate Version file based on Env variable"
	@echo "make release     - Prepare single file for deployment"

gen-version:
	@echo "\"\"\"Version\"\"\"" > gstatus/version.py
	@echo "VERSION = \"${VERSION}\"" >> gstatus/version.py

pytest:
	${PYTHON} -m pytest gstatus

pylint:
	cd gstatus && ${PYTHON} -m pylint --disable W0511 *.py

mypy:
	cd gstatus && ${PYTHON} -m mypy *.py

release: gen-version
	@rm -rf build
	@mkdir -p build/src
	@cp -r gstatus/* build/src/
	@${PYTHON} -m pip install -r requirements.txt --target build/src
	@cd build/src && zip -r ../${PROGNAME}.zip *
	@echo '#!/usr/bin/env ${PYTHON}' | cat - build/${PROGNAME}.zip > build/${PROGNAME}
	@chmod +x build/${PROGNAME}
	@rm -rf build/src
	@rm -f build/${PROGNAME}.zip
	@echo "Single deployment file is ready: build/${PROGNAME}"
