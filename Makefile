.PHONY: format lint test check

format:
	isort .
	black .

lint:
	black --check .
	isort --check .
	flake8 .

test:
	pytest

check: lint test
