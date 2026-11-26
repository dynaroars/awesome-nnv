PYTHON ?= python3

install:
	sudo pacman -S hugo
	pip install networkx

fetch:
	cd backend/code && $(PYTHON) fetch_dblp.py && $(PYTHON) fetch_virtual.py && $(PYTHON) fetch_researchr.py

refresh:
	cd backend/code && $(PYTHON) fetch_dblp.py --refresh && $(PYTHON) fetch_virtual.py --refresh && $(PYTHON) fetch_researchr.py --refresh && $(PYTHON) scan_topics.py && $(PYTHON) find_candidates.py

topics:
	cd backend/code && $(PYTHON) scan_topics.py

candidates:
	cd backend/code && $(PYTHON) find_candidates.py && $(PYTHON) fetch_people.py && $(PYTHON) find_candidates.py

pdfs:
	cd backend/code && zsh -ic '$(PYTHON) fetch_pdfs.py'

reviews:
	cd backend/code && zsh -ic '$(PYTHON) fetch_reviews.py'

citations:
	cd backend/code && zsh -ic '$(PYTHON) fetch_citations.py'

people:
	cd backend/code && $(PYTHON) fetch_people.py

data:
	cd backend/code && $(PYTHON) find_candidates.py && $(PYTHON) site_affiliations.py && $(PYTHON) build_site_data.py

run:
	cd frontend && hugo serve --buildDrafts --noHTTPCache --disableFastRender

build:
	rm -rf frontend/public
	cd frontend && hugo

PAGES_REPO ?= dynaroars/awesome-nnv
PAGES_REMOTE ?= $(shell git remote get-url origin)
GIT_NAME := $(shell git config user.name)
GIT_EMAIL := $(shell git config user.email)

publish:
	rm -rf frontend/public
	cd frontend && hugo --config hugo.toml,publish.toml
	touch frontend/public/.nojekyll
	cd frontend/public && git init -q -b gh-pages && git add -A \
		&& TZ=UTC git -c user.name="$(GIT_NAME)" -c user.email="$(GIT_EMAIL)" commit -q -m "site of $$(date -u +%F)" \
		&& git push -f $(PAGES_REMOTE) gh-pages
	rm -rf frontend/public/.git
	sleep 10
	-gh run watch --repo $(PAGES_REPO) --exit-status \
		$$(gh run list --repo $(PAGES_REPO) --branch gh-pages --limit 1 --json databaseId --jq '.[0].databaseId')

test:
	cd backend/code && $(PYTHON) -m unittest discover -s tests

clean:
	rm -rf frontend/public frontend/resources backend/work
