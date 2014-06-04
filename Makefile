$(eval VERSION := $(shell python setup.py --version))
SDIST := dist/django-locks-$(VERSION).tar.gz

all: build

build: $(SDIST)

$(SDIST):
	python setup.py sdist
	rm -rf django_locks.egg-info

.PHONY: install
install: $(SDIST)
	sudo pip install $(SDIST)

.PHONY: uninstall
uninstall:
	sudo pip uninstall django-locks

.PHONY: register
register:
	python setup.py register

.PHONY: upload
upload:
	python setup.py sdist upload
	rm -rf django_locks.egg-info

.PHONY: clean
clean:
	rm -rf dist django_locks.egg django_locks.egg-info
