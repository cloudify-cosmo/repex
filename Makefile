# Copyright 2015,2016 Nir Cohen
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Name of this package
PACKAGENAME = repex

.PHONY: help
help:
	@echo 'Please use "make <target>" where <target> is one of'
	@echo "  build     - build the package"
	@echo "  dev       - prepare a development environment (includes tests)"
	@echo "  instdev   - prepare a development environment (no tests)"
	@echo "  install   - install into current Python environment"
	@echo "  test      - test from this directory using tox, including test coverage"
	@echo "  publish   - upload to PyPI"
	@echo "  clean     - remove any temporary build products"

.PHONY: dev
dev: instdev test
	@echo "$@ done."

.PHONY: instdev
instdev:
	pip install -r dev-requirements.txt
	python setup.py develop
	@echo "$@ done."

.PHONY: install
install:
	python setup.py install
	@echo "$@ done."

.PHONY: test
test:
	pip install 'tox>=1.7.2'
	tox
	@echo "$@ done."

.PHONY: publish
publish: test clean build
	# assumes there's a .pypirc config for `cosmo`
	twine upload -r cosmo dist/$(PACKAGENAME)-*
	@echo "$@ done."

.PHONY: clean
clean:
	rm -rf build dist $(PACKAGENAME).egg-info
	@echo "$@ done."

.PHONY: build
build:
	python setup.py sdist bdist_wheel