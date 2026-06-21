.PHONY: format lint

format:
	isort .
	black .

lint:
	black --check .
	isort --check .
	flake8 .

