.PHONY: start update migration

start:
	python main.py

update:
	alembic upgrade head

migration:
	alembic revision --autogenerate -m "$(name)"