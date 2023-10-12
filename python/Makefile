PYTHON_VERSION = 3.9.16

VENV_DIR = .venv
POETRY_VENV_DIR = .poetry-venv

# exports PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring since keyring
# isn't needed for an install operation and some Linux users seem to experience
# problems with newer versions of poetry (v1.2.x) due to this.
# https://github.com/python-poetry/poetry/issues/1917#issuecomment-1235998997
# Dont run this manually via make. Run it through make dev-setup
.PHONY: dev-setup
dev-setup: export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring
dev-setup:
	pyenv local $(PYTHON_VERSION)

	python -m venv $(POETRY_VENV_DIR)
	$(POETRY_VENV_DIR)/bin/pip install --upgrade pip
	$(POETRY_VENV_DIR)/bin/pip install poetry==1.4.2

	python -m venv $(VENV_DIR)
	$(VENV_DIR)/bin/pip install --upgrade pip
	$(POETRY_VENV_DIR)/bin/poetry install
	$(VENV_DIR)/bin/pre-commit install -ft pre-commit

.PHONY: pyenv
pyenv:
	pyenv install -s $(PYTHON_VERSION)
