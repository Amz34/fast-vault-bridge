.PHONY: test lint clean run

test:
	python3 -m unittest discover -s tests -v

lint:
	python3 -m py_compile fast_vault/*.py tests/*.py

clean:
	rm -rf __pycache__ fast_vault/__pycache__ tests/__pycache__ /tmp/vault_pack

run:
	python3 -m fast_vault.cli sample-queue
