# BuEM — Building Energy Model

[![Documentation](https://readthedocs.org/projects/buem/badge/?version=latest)](https://buem.readthedocs.io/en/latest/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/downloads/)

BuEM computes **hourly heating and cooling demand** for buildings using the
**ISO 13790 5R1C** thermal-network method combined with a linear-programming
solver. It exposes a REST API that accepts GeoJSON and returns energy profiles,
making it straightforward to integrate with urban energy-system models.

**Full documentation:** <https://buem.readthedocs.io/en/latest/>

---

## Quick Start

```bash
# 1. Clone and create the environment
git clone https://github.com/somadsahoo/buem.git
cd buem
conda env create -f environment.yml
conda activate buem_env

# 2. Verify the installation
buem validate

# 3. Run the thermal model
buem run

# 4. Start the API server (includes Swagger UI)
buem api
# Open http://localhost:5000/api/docs
```

> For detailed installation instructions (conda, Docker, editable install),
> see the [Installation Guide](https://buem.readthedocs.io/en/latest/installation/index.html).

---

## CLI Reference

```
buem <command> [options]
```

| Command | Description |
|---|---|
| `buem run [--plot] [--milp]` | Run the thermal model for a single building |
| `buem api [--dev] [--port N]` | Start the REST API server (Gunicorn / Flask) |
| `buem validate` | Verify the installation and environment |
| `buem version` | Print the installed BuEM version |
| `buem multibuilding [--test MODE] [--workers N]` | Run parallel multi-building processing |

```bash
buem --help            # Show all commands
buem <command> --help  # Show options for a specific command
```

> Full CLI options and examples:
> [Modules → Integration](https://buem.readthedocs.io/en/latest/modules/integration.html)

---

## API Server

BuEM includes a Flask-based HTTP API with interactive **Swagger UI**
documentation.

```bash
buem api          # Start on http://localhost:5000
buem api --dev    # Flask development server
```

| Endpoint | Method | Description |
|---|---|---|
| `/api/process` | POST | Process GeoJSON FeatureCollection (batch) |
| `/api/run` | POST | Run model for a single building config |
| `/api/files/<filename>` | GET | Download result file |
| `/api/health` | GET | Health check |
| `/api/docs` | GET | **Swagger UI** (interactive API browser) |
| `/api/openapi.yaml` | GET | OpenAPI 3.1 specification |

> Full API reference:
> [API Integration](https://buem.readthedocs.io/en/latest/api_integration/index.html)

---

## Docker

```bash
docker compose up          # Start the API in a container
docker compose down        # Stop and remove containers
```

> Docker configuration details:
> [Deployment](https://buem.readthedocs.io/en/latest/deployment/index.html)

---

## Documentation

| Section | Link |
|---|---|
| Introduction & theory | [Introduction](https://buem.readthedocs.io/en/latest/introduction/index.html) |
| Installation (conda, Docker) | [Installation](https://buem.readthedocs.io/en/latest/installation/index.html) |
| Module reference | [Modules](https://buem.readthedocs.io/en/latest/modules/index.html) |
| API integration & schemas | [API Integration](https://buem.readthedocs.io/en/latest/api_integration/index.html) |
| Deployment & production | [Deployment](https://buem.readthedocs.io/en/latest/deployment/index.html) |

---

## Publications

<!-- Add publications here, e.g.:
- Sahoo, S. et al. (2026). *Title*. Journal, Volume(Issue), Pages. doi:...
-->

*Publication list will be added here.*

---

## Acknowledgements

BuEM is developed at **Utrecht University** as part of the
[CETP](https://www.nwo.nl/en/programmes/complementary-energy-transition-policies)
programme, funded by the **NWO** (Dutch Research Council).

Building typology data is derived from the
[TABULA/EPISCOPE](https://episcope.eu/welcome/) project
(IEE TABULA — Typology Approach for Building Stock Energy Assessment).

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file
for details.

---

## Requirements

- Python ≥ 3.13
- Key dependencies: cvxpy, flask, numpy, pandas, pvlib, scipy

> Full dependency list:
> [Installation → Prerequisites](https://buem.readthedocs.io/en/latest/installation/index.html)