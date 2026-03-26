Installation Guide
==================

This section walks you through every step needed to get BuEM running — from
installing prerequisites to configuring Docker or a local conda environment.

Start with the :doc:`prerequisites` page, then follow the guide that matches
your role.

.. toctree::
   :maxdepth: 2

   prerequisites
   docker_installation
   conda_setup
   development_setup

Quick Start
-----------

**For API Integration (Recommended)**

.. code-block:: bash

    docker pull buem:latest
    docker run -d -p 5000:5000 buem:latest

**For Development**

.. code-block:: bash

    git clone <buem-repository>
    cd buem
    conda env create -f environment.yml
    conda activate buem_env

Installation Options
--------------------

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Method
     - Use Case
     - Pros/Cons
   * - Docker Container
     - Production deployment, API integration
     - ✓ Easy deployment, ✓ Isolated environment, ⚠ Container overhead
   * - Conda Environment
     - Development, local analysis
     - ✓ Full control, ✓ Easy debugging, ⚠ Dependency management
   * - Cloud Deployment
     - Scalable production
     - ✓ Auto-scaling, ✓ High availability, ⚠ Cloud complexity

Next Steps
----------

Choose your installation method:

- :doc:`docker_installation` — production deployment
- :doc:`conda_setup` — development work
- :doc:`../deployment/production_deployment` — scalable deployment