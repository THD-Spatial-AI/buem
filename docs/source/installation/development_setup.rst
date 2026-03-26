Development Setup
=================

Setting up BuEM for development and contribution.

Development Prerequisites
-------------------------

See :doc:`prerequisites` for the full software requirements table.

* Git
* Python >= 3.13
* Conda
* IDE with Python support (VS Code or PyCharm recommended)

Development Installation
------------------------

.. code-block:: bash

    # Fork and clone the repository
    git clone https://github.com/your-username/buem.git
    cd buem
    
    # Create development environment
    conda env create -f environment.yml
    conda activate buem_env
    
    # Install dev dependencies (optional)
    pip install pytest pytest-cov black flake8 mypy
    
    # Install pre-commit hooks (optional)
    # pip install pre-commit
    # pre-commit install

.. note::
   **Important:** When working with the conda environment, always use ``python -m src.buem.main`` 
   to run BUEM commands to avoid import path conflicts. The source code structure requires 
   the ``src.`` prefix when importing modules directly from the repository.

Code Quality Tools
------------------

**Formatting and Linting:**

.. code-block:: bash

    # Format code with black
    black src/ tests/
    
    # Check code style
    flake8 src/ tests/
    
    # Sort imports
    isort src/ tests/

**Pre-commit Configuration:**

Create ``.pre-commit-config.yaml``:

.. code-block:: yaml

    repos:
      - repo: https://github.com/psf/black
        rev: 22.3.0
        hooks:
          - id: black
      - repo: https://github.com/pycqa/flake8
        rev: 4.0.1
        hooks:
          - id: flake8
      - repo: https://github.com/pycqa/isort
        rev: 5.10.1
        hooks:
          - id: isort

Testing Framework
-----------------

**Running Tests:**

.. code-block:: bash

    # Run all tests
    pytest
    
    # Run with coverage
    pytest --cov=buem --cov-report=html
    
    # Run specific test file
    pytest tests/test_api.py
    
    # Run tests with verbose output
    pytest -v

**Test Structure:**

.. code-block:: text

    tests/
    ├── test_api.py           # API endpoint tests
    ├── test_config.py        # Configuration tests
    ├── test_models.py        # Model functionality tests
    ├── test_integration.py   # Integration tests
    └── fixtures/
        ├── sample_buildings.json
        └── test_responses.json

Building Documentation
----------------------

.. code-block:: bash

    # Ensure conda environment is active
    conda activate buem_env
    
    # Build documentation
    cd docs
    make html
    
    # Serve locally
    python -m http.server 8000 -d build/html
    
    # Clean build
    make clean

Contribution Workflow
---------------------

1. **Create Feature Branch:**

.. code-block:: bash

    git checkout -b feature/your-feature-name

2. **Make Changes and Test:**

.. code-block:: bash

    # Edit code
    # Add tests
    pytest
    
3. **Format and Lint:**

.. code-block:: bash

    black src/ tests/
    flake8 src/ tests/
    
4. **Commit and Push:**

.. code-block:: bash

    git add .
    git commit -m "Add feature: description"
    git push origin feature/your-feature-name

5. **Create Pull Request**

Debugging Configuration
-----------------------

**VS Code Settings:**

Create ``.vscode/settings.json``:

.. code-block:: json

    {
        "python.defaultInterpreterPath": "./venv/bin/python",
        "python.formatting.provider": "black",
        "python.linting.enabled": true,
        "python.linting.flake8Enabled": true,
        "python.testing.pytestEnabled": true,
        "python.testing.pytestArgs": ["tests/"]
    }