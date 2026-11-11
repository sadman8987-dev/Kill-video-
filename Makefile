.PHONY: install run test lint docker logs

install:
	pip install -r requirements-dev.txt

run:
	python -m bot

test:
	python -m unittest discover -s tests -t . -v

lint:
	ruff check .

docker:
	docker compose up -d --build

logs:
	docker compose logs -f bot
