import argparse
import sys

from database.connection import SessionLocal

from .reduce import reduce_linestring_from_recording_session


def _line_points(x0: int, y0: int, x1: int, y1: int):
    """Interpolate line segment; yields (x, y) grid cells."""
    n = max(abs(x1 - x0), abs(y1 - y0), 1)
    for i in range(n + 1):
        t = i / n
        yield int(x0 + t * (x1 - x0)), int(y0 + t * (y1 - y0))


def _render_path_overlay(
    lons_before: list[float],
    lats_before: list[float],
    lons_after: list[float],
    lats_after: list[float],
    *,
    width: int = 60,
    height: int = 15,
) -> str:
    """
    Overlay both paths on the same grid to show the difference.

    · = removed by simplification (original only)
    * = kept (simplified path)
    ● = start, ○ = end
    """
    all_lons = lons_before + lons_after
    all_lats = lats_before + lats_after
    if len(all_lons) < 2:
        return "(no path)"

    min_lon, max_lon = min(all_lons), max(all_lons)
    min_lat, max_lat = min(all_lats), max(all_lats)
    pad = 0.15
    rng_lon = max(max_lon - min_lon, 0.00001)
    rng_lat = max(max_lat - min_lat, 0.00001)
    pad_lon = max(rng_lon * pad, 0.00001)
    pad_lat = max(rng_lat * pad, 0.00001)
    min_lon -= pad_lon
    max_lon += pad_lon
    min_lat -= pad_lat
    max_lat += pad_lat
    rng_lon = max_lon - min_lon
    rng_lat = max_lat - min_lat

    grid = [[" " for _ in range(width)] for _ in range(height)]

    def to_col(lon: float) -> int:
        return int((lon - min_lon) / rng_lon * (width - 1))

    def to_row(lat: float) -> int:
        return height - 1 - int((lat - min_lat) / rng_lat * (height - 1))

    def plot(x: int, y: int, ch: str) -> None:
        if 0 <= y < height and 0 <= x < width:
            grid[y][x] = ch

    # Draw original path first (removed segments)
    for i in range(len(lons_before) - 1):
        x0, y0 = to_col(lons_before[i]), to_row(lats_before[i])
        x1, y1 = to_col(lons_before[i + 1]), to_row(lats_before[i + 1])
        for x, y in _line_points(x0, y0, x1, y1):
            plot(x, y, "·")

    # Overdraw simplified path (kept segments)
    for i in range(len(lons_after) - 1):
        x0, y0 = to_col(lons_after[i]), to_row(lats_after[i])
        x1, y1 = to_col(lons_after[i + 1]), to_row(lats_after[i + 1])
        for x, y in _line_points(x0, y0, x1, y1):
            plot(x, y, "*")

    # Mark start and end
    plot(to_col(lons_before[0]), to_row(lats_before[0]), "●")
    plot(to_col(lons_before[-1]), to_row(lats_before[-1]), "○")

    return "\n".join("".join(row) for row in grid)


def _cmd_simplify(args: argparse.Namespace) -> int:
    db = SessionLocal()
    try:
        result = reduce_linestring_from_recording_session(
            db,
            args.record_id,
            tolerance=args.tolerance,
            return_coords=getattr(args, "visualize", False),
        )
        db.commit()

        if getattr(args, "visualize", False) and "coords_before" in result:
            before = result["coords_before"]
            after = result["coords_after"]
            print("\n  Overlay: · = removed, * = kept, ● = start, ○ = end\n")
            print(
                _render_path_overlay(
                    [c[0] for c in before],
                    [c[1] for c in before],
                    [c[0] for c in after],
                    [c[1] for c in after],
                )
            )
            print(f"\n  Before: {len(before)} points  →  After: {len(after)} points\n")

        print(
            f"Simplified: {result['points_before']} -> {result['points_after']} points "
            f"({result['points_removed']} removed)"
        )
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(prog="geodata")
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
        metavar="command",
        help="Command to run",
    )

    simplify_parser = subparsers.add_parser("simplify", help="Simplify a recording session path (RDP)")
    simplify_parser.add_argument("record_id", type=int, help="Recording session ID")
    simplify_parser.add_argument(
        "--tolerance",
        type=float,
        default=0.00005,
        help="RDP tolerance in degrees (WGS84); default 0.00005 (~5 m)",
    )
    simplify_parser.add_argument(
        "-v",
        "--visualize",
        action="store_true",
        help="Print ASCII preview of path before and after simplification",
    )
    simplify_parser.set_defaults(handler=_cmd_simplify)

    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
