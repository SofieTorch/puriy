"""Human-readable street + neighbourhood labels for reconstructed routes.

Two helpers consumed by `pipeline.steps.reconstruct_routes._save_reconstruction`:

- `summarise_streets`: walks the Valhalla `trace_match` edges and emits
  the ordered list of street/avenue names the route runs along, dropping
  cross-streets via a minimum run-length filter.
- `resolve_endpoint_zones`: reverse-geocodes the route's first/last
  polyline points to neighbourhood names (Beijing, Sacaba, …) via
  Nominatim. Tolerates failures — returns `None` for either side that
  doesn't resolve.

Both feed RF-07 ("show destinations textually") and the ramal identity
copy on the descriptor screen.
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

#: Local Nominatim endpoint by default (the user runs one in
#: `infra/local`). Override with `NOMINATIM_URL` to hit a different
#: instance. Public Nominatim works too but rate-limits aggressively.
NOMINATIM_URL_DEFAULT = "http://localhost:8088"

#: Admin levels in OSM that map to "neighbourhood" / "zone" in
#: Cochabamba's reverse-geocoded output. Tried in order; first hit wins.
_ZONE_FIELDS = ("suburb", "neighbourhood", "quarter", "city_district", "village", "town")


def summarise_streets(
    edges: list[dict],
    *,
    min_run_m: float = 200.0,
) -> list[str]:
    """Order Valhalla matched edges into street-name segments.

    Walks `edges` in order, groups consecutive edges sharing the same
    primary name (`edge["names"][0]`), and emits the name once per
    consecutive group whose total run-length is at least `min_run_m`
    metres. Edges without names or with empty `names` are treated as
    "name break" — they end the current group without contributing to it.

    Parameters
    ----------
    edges
        Valhalla `trace_attributes` edge dicts. Each is expected to
        have `names: list[str]` and `length: float` (kilometres).
    min_run_m
        Minimum cumulative length of consecutive same-named edges to
        emit the name. ~200m drops cross-street crossings while keeping
        every street the route actually travels along.

    Returns
    -------
    list[str]
        Street names in the order the route traverses them. Empty if
        no edges meet the threshold or all edges lack names.
    """
    out: list[str] = []
    current_name: str | None = None
    current_length_m: float = 0.0

    def _flush() -> None:
        nonlocal current_name, current_length_m
        if current_name is not None and current_length_m >= min_run_m:
            # De-duplicate immediately-repeated names (a one-block detour
            # that returns to the same avenue shouldn't list it twice).
            if not out or out[-1] != current_name:
                out.append(current_name)
        current_name = None
        current_length_m = 0.0

    for edge in edges:
        names = edge.get("names") or []
        length_km = float(edge.get("length", 0.0) or 0.0)
        length_m = length_km * 1000.0
        name = names[0] if names else None

        if name is None or name == "":
            _flush()
            continue

        if name == current_name:
            current_length_m += length_m
        else:
            _flush()
            current_name = name
            current_length_m = length_m

    _flush()
    return out


def resolve_endpoint_zones(
    start_lon_lat: list[float],
    end_lon_lat: list[float],
    *,
    nominatim_url: str | None = None,
    timeout_s: float = 5.0,
) -> list[str | None]:
    """Reverse-geocode the route's endpoints to neighbourhood names.

    Returns `[start_zone, end_zone]`. Either entry is `None` if
    Nominatim doesn't return a usable result (network failure, no
    matching admin level, malformed input, …) — never raises.
    """
    base_url = nominatim_url or os.environ.get("NOMINATIM_URL", NOMINATIM_URL_DEFAULT)
    return [
        _reverse_geocode_zone(start_lon_lat, base_url, timeout_s),
        _reverse_geocode_zone(end_lon_lat, base_url, timeout_s),
    ]


def _reverse_geocode_zone(
    lon_lat: list[float], base_url: str, timeout_s: float,
) -> str | None:
    if not lon_lat or len(lon_lat) < 2:
        return None
    try:
        resp = httpx.get(
            f"{base_url.rstrip('/')}/reverse",
            params={
                "lon": lon_lat[0],
                "lat": lon_lat[1],
                "format": "jsonv2",
                "zoom": 16,        # neighbourhood-ish zoom
                "addressdetails": 1,
            },
            headers={"User-Agent": "puriy-cbba-mobility/1.0"},
            timeout=timeout_s,
        )
        resp.raise_for_status()
        addr = (resp.json() or {}).get("address", {}) or {}
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning(
            "nominatim reverse-geocode failed for %s: %s", lon_lat, exc,
        )
        return None

    for field in _ZONE_FIELDS:
        value = addr.get(field)
        if value:
            return str(value)
    return None
