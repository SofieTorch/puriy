"""Convert GTFS shapes + routes to one GeoJSON file per route."""

import csv
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(DIR, "geojson")


def read_csv(filename):
    with open(os.path.join(DIR, filename)) as f:
        return list(csv.DictReader(f))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    routes = {r["route_id"]: r for r in read_csv("routes.txt")}

    # Group shape points by shape_id, ordered by sequence
    shapes: dict[str, list] = {}
    for pt in read_csv("shapes.txt"):
        shapes.setdefault(pt["shape_id"], []).append(pt)
    for pts in shapes.values():
        pts.sort(key=lambda p: int(p["shape_pt_sequence"]))

    # Find which shape_id belongs to each route (via trips)
    route_shapes: dict[str, str] = {}
    for trip in read_csv("trips.txt"):
        route_shapes[trip["route_id"]] = trip["shape_id"]

    for route_id, route in routes.items():
        shape_id = route_shapes.get(route_id)
        if not shape_id or shape_id not in shapes:
            print(f"Skipping route {route['route_short_name']}: no shape data")
            continue

        coords = [
            [float(pt["shape_pt_lon"]), float(pt["shape_pt_lat"])]
            for pt in shapes[shape_id]
        ]

        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "route_id": route_id,
                        "route_short_name": route["route_short_name"],
                        "route_long_name": route["route_long_name"],
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": coords,
                    },
                }
            ],
        }

        name = route["route_short_name"].replace(" ", "_").replace("/", "-")
        out_path = os.path.join(OUT_DIR, f"{name}.geojson")
        with open(out_path, "w") as f:
            json.dump(geojson, f, indent=2)
        print(f"Wrote {out_path} ({len(coords)} points)")


if __name__ == "__main__":
    main()
