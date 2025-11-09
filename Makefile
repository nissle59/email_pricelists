.PHONY: start update migration build-mac

start:
	python main.py

update:
	alembic upgrade head

migration:
	alembic revision --autogenerate -m "$(name)"

build-mac:
	bash build_mac_dmg.sh