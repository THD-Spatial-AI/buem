import json
from pathlib import Path

import requests

API_URL = "http://127.0.0.1:5000/api/process"
RESPONSE_FILE = Path(r"c:\\test\\buem\\src\\buem\\integration\\api_response_received_v1.geojson")

def main():
    # Example structured payload: includes `components` object (no legacy keys)
    payload = {
      "type": "FeatureCollection",
      "timeStamp": "2025-12-03T00:00:00Z",
      "numberMatched": 1,
      "numberReturned": 1,
      "features": [
        {
          "type": "Feature",
          "id": "building_1",
          "geometry": {"type": "Point", "coordinates": [12.4924, 41.8902]},
          "properties": {
            "buem": {
              "building_attributes": {
                "components": {
                  "Walls": {
                    "U": 0.5,
                    "elements": [{"id": "w1", "area": 150.0}]
                  },
                  "Windows": {
                    "U": 1.6,
                    "elements": [{"id": "win1", "area": 12.0}]
                  },
                  "Roof": {
                    "U": 0.2,
                    "elements": [{"id": "r1", "area": 200.0}]
                  },
                  "Floor": {
                    "U": 0.3,
                    "elements": [{"id": "f1", "area": 200.0}]
                  },
                  "Doors": {
                    "elements": [{"id": "d1", "area": 5.0, "U": 2.0}]
                  }
                },
                # short time series for testing (length should be consistent across relevant arrays)
                "elecLoad": [0.5, 0.5, 0.5],
                "Q_ig": [0.1, 0.1, 0.1],
                # lightweight weather sample (index length matches elecLoad/Q_ig)
                "weather": {
                  "index": ["2025-01-01T00:00:00Z", "2025-01-01T01:00:00Z", "2025-01-01T02:00:00Z"],
                  "T": [10.0, 9.5, 9.0],
                  "GHI": [0.0, 0.0, 0.0]
                }
              },
              "child_components": []
            }
          }
        }
      ]
    }

    # adjust timeout > expected model runtime (ModelBUEM ~16s per building)
    r = requests.post(API_URL, json=payload, timeout=120)
    print("Status:", r.status_code)
    if r.status_code == 200:
        RESPONSE_FILE.write_text(json.dumps(r.json(), indent=2), encoding="utf-8")
        print("Saved response to", RESPONSE_FILE)
    else:
        print("Error response:", r.status_code, r.text)

if __name__ == "__main__":
    main()