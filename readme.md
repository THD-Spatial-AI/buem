# BUEM: Building Thermal Model

BUEM is a Python module for simulating building thermal behavior using the ISO 52016-1:2017 5R1C model.  
It supports solar gains, detailed heat load calculations, and the possibility to solve inequalities 
related to temperature ranges and other bounded conditions.

## Features

- 5R1C thermal model (ISO 52016-1)
- Refurbishment and insulation options
- Solar and internal gains
- Heating and cooling load calculation
- Plotting of results

## Installation

### Method 1: Conda Environment (Recommended)

1. Clone the repository:
   ```bash
   git clone https://github.com/somadsahoo/buem.git
   cd buem
   ```

2. Create and activate the conda environment:
   ```bash
   conda env create -f environment.yml
   conda activate buem_env
   ```

   **Note:** The environment includes `psycopg2` for PostgreSQL database access (e.g. city2tabula).

### Method 2: PyPI Installation

```bash
pip install buem
```

## Conda install (for advanced users)

To build and install with conda:

```bash
   conda install conda-build
   conda build .
   conda install --use-local buem
```

## Docker Setup and Usage

For a fully reproducible environment:

```bash
docker compose up
```

**Note:** Output files will be saved to the `output/` directory if configured.

## Usage

### Command Line

**With conda environment (recommended):**
```bash
conda activate buem_env
python -m src.buem.main
```

**With PyPI installation:**
```bash
python -m buem.main
# or simply:
buem
```

### Python Scripts

```python
from buem.thermal.model_buem import ModelBUEM
from buem.config.cfg_attribute import cfg

model = ModelBUEM(cfg)
model.sim_model(use_inequality_constraints=False)
```

**Note:** When working with the conda environment, use `python -m src.buem.main` to avoid import path conflicts.

## API Server

BUEM includes a Flask-based HTTP API for processing building models and GeoJSON data.

### Starting the Server

**With conda environment:**
```bash
conda activate buem_env
python -m src.buem.apis.api_server
```

**With PyPI installation:**
```bash
python -m buem.apis.api_server
```

Server runs on `http://localhost:5000` by default.

### Quick API Examples

**Health check:**
```bash
curl http://localhost:5000/api/health
```

**Process GeoJSON:**
```bash
curl -X POST "http://localhost:5000/api/process" \
   -H "Content-Type: application/json" \
   -d @src/buem/integration/json_schema/versions/v2/example_request.json
```

**Available Endpoints:**
- `GET /api/health` - Health check
- `POST /api/run` - Run thermal model with JSON config  
- `POST /api/process` - Process GeoJSON features
- `GET /api/files/<filename>` - Download result files

**Query Parameters:**
- `?include_timeseries=true` - Include full time series data

For detailed API documentation, examples, and troubleshooting, see [docs/api_integration/](docs/api_integration/).

---

## Requirements

- Python 3.13+

Other python-based modules
--------------------------
- matplotlib
- numpy
- pandas
- pvlib
- scipy
- sympy
- openpyxl
- cvxpy
- numba
- flask
- pulp
- psutil
- joblib

## Notes

- **Import Structure**: When using the conda environment, always use `python -m src.buem.main` to avoid import conflicts with the source code structure
- **Docker**: Use `docker compose up` for containerized deployment  
- **Configuration**: Custom settings can be edited in `src/buem/config/`
- **Output files**: Saved to `output/` directory when configured
- **API Documentation**: Detailed API examples and configuration in [docs/api_integration/](docs/api_integration/)

---

## License

MIT