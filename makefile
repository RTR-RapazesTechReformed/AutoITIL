format:
	cd backend && ruff format .
	cd backend && ruff check . --fix

lint:
	cd backend && ruff check .

test:
	cd backend && python -m pytest

cov:
	cd backend && python -m pytest --cov=app