# BuEM Documentation

This repository contains the documentation for
the Building Energy Model (BuEM) package, specifically
designed for developers integrating BuEM with other models
via APIs through Docker containers.

## About BuEM

BuEM is a comprehensive thermal simulation tool for building
energy analysis. It provides:

- Thermal load calculations for heating and cooling
- REST API for model integration
- Docker containerization support
- Comprehensive building attribute system

## Documentation Structure

The documentation is organized into the following sections:

- **Introduction**: Overview of BuEM and its capabilities
- **API Integration**: Detailed guide for developers on API usage
- **Model Attributes**: Complete reference of building attributes and data exchange formats
- **Technical Reference**: In-depth technical documentation
- **Installation**: Setup and deployment instructions
- **Examples**: Practical examples and use cases

## Online Documentation

This documentation is hosted at: [https://buem.readthedocs.io/](https://buem.readthedocs.io/)

## Local Development

To generate the documentation locally:

### Prerequisites

Make sure you have the BuEM conda environment activated:

```shell
conda activate buem_env
```

Install documentation dependencies:

```shell
pip install -r docs/requirements.txt
```

### Building Documentation

```shell
cd docs
make html
```

Then the HTML is generated in the directory `docs/build/html`.
Open the `index.html` in that directory in your browser to see your changes.

### Alternative Build Commands

```shell
# Clean previous build
make clean

# Build HTML documentation
make html

# Build PDF documentation (if LaTeX is installed)
make latexpdf
```

## Contributing

When contributing to the documentation:

1. Use reStructuredText (.rst) format
2. Follow the existing structure and style
3. Test builds locally before submitting
4. Focus on developer-oriented content for API integration

## Automatic Deployment

When changes are pushed to the main branch, the online documentation
is automatically regenerated within a few minutes through ReadTheDocs integration.

## License

This documentation is part of the BuEM project and follows the same license terms.
