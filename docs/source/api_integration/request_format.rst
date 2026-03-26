Request Data Format
===================

BuEM accepts building data in GeoJSON format. This section details the exact structure and requirements for API requests.

GeoJSON Structure
-----------------

**Top Level**

.. code-block:: javascript

    {
      "type": "FeatureCollection",
      "timeStamp": "2018-01-22T00:00:00Z",
      "numberMatched": 1,
      "numberReturned": 1,
      "features": [/* ... */]
    }

**Feature Structure**

Each building is represented as a GeoJSON Feature:

.. code-block:: javascript

    {
      "type": "Feature",
      "id": "B001",
      "geometry": {
        "type": "Point",
        "coordinates": [-0.1278, 51.5074]
      },
      "properties": {
        "buem": {
          "building_attributes": {/* ... */},
          "use_milp": false
        }
      }
    }

Required Fields
---------------

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Field
     - Type
     - Description
   * - ``type``
     - string
     - Must be "Feature" or "FeatureCollection"
   * - ``id``
     - string
     - Unique identifier for the building
   * - ``geometry``
     - object
     - GeoJSON geometry (Point recommended)
   * - ``properties.buem.building_attributes``
     - object
     - Building configuration parameters

Building Attributes Structure
-----------------------------

The ``building_attributes`` object contains all building configuration data:

**Basic Properties**

.. code-block:: json

    {
      "latitude": 51.5074,
      "longitude": -0.1278,
      "A_ref": 100.0,
      "h_room": 2.5
    }

**Components Structure**

The ``components`` object defines building envelope elements:

.. code-block:: json

    {
      "components": {
        "Walls": {
          "U": 1.6,
          "elements": [
            {
              "id": "Wall_1",
              "area": 50.0,
              "azimuth": 0.0,
              "tilt": 0.0
            }
          ]
        },
        "Roof": {
          "U": 1.5,
          "elements": [
            {
              "id": "Roof_1",
              "area": 40.0,
              "azimuth": 180.0,
              "tilt": 30.0
            }
          ]
        },
        "Floor": {
          "U": 1.7,
          "elements": [
            {
              "id": "Floor_1",
              "area": 100.0,
              "azimuth": 0.0,
              "tilt": 90.0
            }
          ]
        },
        "Windows": {
          "U": 2.5,
          "g_gl": 0.5,
          "elements": [
            {
              "id": "Win_1",
              "area": 8.0,
              "surface": "Wall_1",
              "azimuth": 0.0,
              "tilt": 0.0
            }
          ]
        },
        "Doors": {
          "U": 3.5,
          "elements": [
            {
              "id": "Door_1",
              "area": 2.0,
              "surface": "Wall_1",
              "azimuth": 0.0,
              "tilt": 0.0
            }
          ]
        },
        "Ventilation": {
          "elements": [
            {
              "id": "Vent_1",
              "air_changes": 0.5
            }
          ]
        }
      }
    }

Component Types
---------------

**Walls**

.. list-table::
   :header-rows: 1
   :widths: 20 15 15 50

   * - Field
     - Type
     - Required
     - Description
   * - ``U``
     - number
     - Yes
     - U-value (W/m²K)
   * - ``b_transmission``
     - number
     - No
     - Transmission adjustment factor (default: 1.0)
   * - ``elements[].id``
     - string
     - Yes
     - Unique element identifier
   * - ``elements[].area``
     - number
     - Yes
     - Element area (m²)
   * - ``elements[].azimuth``
     - number
     - Yes
     - Orientation angle (degrees, 0=North)
   * - ``elements[].tilt``
     - number
     - Yes
     - Tilt angle (degrees, 0=horizontal, 90=vertical)

**Roof**

Same structure as Walls.

**Floor**

Same structure as Walls.

**Windows**

.. list-table::
   :header-rows: 1
   :widths: 20 15 15 50

   * - Field
     - Type
     - Required
     - Description
   * - ``U``
     - number
     - Yes
     - U-value (W/m²K)
   * - ``g_gl``
     - number
     - Yes
     - Solar energy transmittance (0-1)
   * - ``elements[].surface``
     - string
     - No
     - ID of parent surface element

**Doors**

Same structure as Walls.

**Ventilation**

.. list-table::
   :header-rows: 1
   :widths: 20 15 15 50

   * - Field
     - Type
     - Required
     - Description
   * - ``elements[].air_changes``
     - number
     - Yes
     - Air changes per hour

Optional Configuration
----------------------

**Occupancy Settings**

.. code-block:: json

    {
      "num_persons": 4,
      "year": 2018,
      "seed": 12345,
      "use_provided_elecLoad": false
    }

**Comfort Settings**

.. code-block:: json

    {
      "comfortT_lb": 21.0,
      "comfortT_ub": 24.0,
      "thermalClass": "medium"
    }

**Advanced Options**

.. code-block:: json

    {
      "use_milp": false,
      "design_T_min": -12.0,
      "n_air_infiltration": 0.5
    }

Complete Example
----------------

Here's a complete minimal request:

.. code-block:: json

    {
      "type": "FeatureCollection",
      "features": [
        {
          "type": "Feature",
          "id": "B001",
          "geometry": { "type": "Point", "coordinates": [-0.1278, 51.5074] },
          "properties": {
            "buem": {
              "building_attributes": {
                "latitude": 51.5074,
                "longitude": -0.1278,
                "A_ref": 100.0,
                "h_room": 2.5,
                "components": {
                  "Walls": {
                    "U": 1.6,
                    "elements": [
                      { "id": "Wall_1", "area": 50.0, "azimuth": 0.0, "tilt": 0.0 }
                    ]
                  },
                  "Roof": {
                    "U": 1.5,
                    "elements": [
                      { "id": "Roof_1", "area": 40.0, "azimuth": 180.0, "tilt": 30.0 }
                    ]
                  },
                  "Floor": {
                    "U": 1.7,
                    "elements": [
                      { "id": "Floor_1", "area": 100.0, "azimuth": 0.0, "tilt": 90.0 }
                    ]
                  },
                  "Windows": {
                    "U": 2.5,
                    "g_gl": 0.5,
                    "elements": [
                      { "id": "Win_1", "area": 8.0, "surface": "Wall_1", "azimuth": 0.0, "tilt": 0.0 }
                    ]
                  },
                  "Ventilation": { 
                    "elements": [ 
                      { "id": "Vent_1", "air_changes": 0.5 } 
                    ] 
                  }
                }
              }
            }
          }
        }
      ]
    }

Validation Rules
----------------

**Coordinate System**
- Latitude: -90 to 90 degrees
- Longitude: -180 to 180 degrees
- Azimuth: 0 to 360 degrees (0 = North, 90 = East, 180 = South, 270 = West)
- Tilt: 0 to 90 degrees (0 = horizontal, 90 = vertical)

**Physical Constraints**
- All areas must be positive numbers
- U-values must be positive  
- g_gl values must be between 0 and 1
- Air changes must be positive

**Component Requirements**
- At least one element required for each component type
- Window elements should reference valid wall surfaces
- Total window area should not exceed parent wall area

Next Steps
----------

Continue to :doc:`response_format` to understand the output data format.