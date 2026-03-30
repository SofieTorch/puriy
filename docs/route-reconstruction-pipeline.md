# Route Reconstruction Pipeline

This document describes the full pipeline used to reconstruct transit routes from crowdsourced GPS recordings. It covers every step, every design decision, every parameter, and every library involved, in the order the data flows through the system.

The pipeline has five stages:

```
Raw GPS recordings
      ↓
[1] Map-matching (Valhalla / Meili HMM)   → Trip + TripPoints
      ↓
[2] Quality filtering (match_score)
      ↓
[3] Resampling to uniform distance        → ResampledTrip + ResampledTripPoints
      ↓
[4] Direction validation                  → TripDirection labels
      ↓
[5] DBSCAN clustering                     → RouteEstimation + RouteSegments
```

---

## Data Model Overview

Before the pipeline steps, here is the full table graph that data moves through:

| Table | Description |
|---|---|
| `lines` | A named transit route (e.g. "Line 101") |
| `trip_sessions` | A raw GPS recording session from a user's device |
| `trip_session_points` | Individual raw GPS points within a session |
| `trip_sensor_readings` | Accelerometer / gyroscope / barometer readings from the same session |
| `trips` | A cleaned, map-matched version of a `trip_session` |
| `trip_points` | Snapped GPS points after map-matching, one per original input point |
| `resampled_trips` | A trip re-sampled to uniform distance intervals |
| `resampled_trip_points` | The uniformly-spaced points of a resampled trip |
| `route_estimations` | A DBSCAN-derived consensus route for a line (versioned) |
| `route_segments` | Individual LineString chunks of an estimation, the unit of user voting |
| `segment_votes` | A user vote (approve/reject) on a segment, backed by a trip |
| `travel_time_samples` | Travel time measurements for A→B estimation, linked to segments |

All primary keys are UUID v4 (generated at insert time). All geometries are stored in PostGIS with SRID 4326 (WGS-84).

---

## Step 1 — Raw GPS Collection

**Files:** `database/models/trip.py`

A user on the mobile app starts a recording session, which creates a `TripSession` row. As the user moves, the app streams GPS points in batches to the API, which stores each one as a `TripSessionPoint`.

### TripSession fields

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `line_id` | UUID FK | Which transit line is being recorded |
| `direction` | str (optional) | Free-text direction hint from the app (e.g. "northbound") — not used algorithmically |
| `device_id` | str | Hashed device identifier |
| `device_model` | str | e.g. "iPhone 15" — useful for debugging GPS quality issues |
| `os_version` | str | iOS/Android version |
| `status` | `SessionStatus` | Lifecycle: `in_progress → completed / cancelled / abandoned / discarded` |
| `processing_status` | `ProcessingStatus` | Pipeline: `raw → processing → processed / failed` |
| `computed_path` | PostGIS LINESTRING | Built server-side from uploaded points when the session ends |
| `started_at` | datetime | Session start |
| `ended_at` | datetime | Session end (set when status → completed) |
| `last_activity_at` | datetime | Updated on every batch upload — used to detect abandoned sessions |

### TripSessionPoint fields

| Field | Type | Notes |
|---|---|---|
| `timestamp` | datetime (UTC) | The GPS fix timestamp from the device |
| `latitude` / `longitude` | float | WGS-84 coordinates |
| `altitude` | float (optional) | Metres above sea level — not used in pipeline |
| `speed` | float (optional) | Metres per second from GPS — not used in pipeline |
| `bearing` | float 0–360 (optional) | Degrees from north — not used in pipeline |
| `horizontal_accuracy` | float (optional) | GPS horizontal accuracy estimate in metres |
| `vertical_accuracy` | float (optional) | GPS vertical accuracy estimate in metres |
| `point` | PostGIS POINT | Duplicate of lat/lon in spatial column for PostGIS operations |

The device also records sensor data in `TripSensorReading` (accelerometer XYZ, gyroscope XYZ, barometric pressure, magnetic heading), but this is not currently used in the route reconstruction pipeline.

### Which sessions enter the pipeline

Only sessions with:
- `status = COMPLETED` — the user finished the recording normally
- `processing_status = RAW` — not yet processed

Cancelled, abandoned, and discarded sessions are excluded. Sessions are considered eligible only after the user explicitly ends them.

---

## Step 2 — Map-Matching with Valhalla / Meili HMM

**File:** `packages/geodata/src/geodata/match.py`
**External service:** Valhalla routing engine (self-hosted, default `http://localhost:8002`)
**Library:** `httpx` (for the HTTP call to Valhalla)

### GPS Noise — The Problem Being Solved

Before explaining the solution, it is important to understand the specific types of noise present in raw GPS data. These vary in cause, magnitude, and distribution, and each affects the pipeline differently.

**1. Random positional noise (multipath and atmospheric delays)**

GPS works by measuring the travel time of signals from multiple satellites. Any delay or distortion in those signals translates directly into position error. Two common sources:

- *Multipath*: GPS signals bounce off buildings, vehicles, and other reflective surfaces before reaching the antenna. The receiver picks up both the direct signal and one or more reflected copies, and their superposition distorts the time-of-arrival measurement. In urban environments this causes errors of 5–30 m and is the dominant noise source.
- *Atmospheric delays*: The ionosphere and troposphere slow GPS signals at rates that vary by time of day, solar activity, and weather. Modern receivers model and partially correct for these, but residual errors of 3–10 m remain.

This noise is approximately Gaussian: most points are within 5–10 m of the true position, with rare outliers reaching 30–50 m. The HMM emission model is specifically designed to handle this distribution.

**2. Urban canyon effect**

When a bus travels through a narrow street flanked by tall buildings, the buildings block all satellites except those almost directly overhead. This reduces the number of visible satellites from a typical 8–12 to 3–4, and more critically, all of them are in a narrow cone above. The resulting position estimate has very high geometric dilution of precision (GDOP) — errors that would normally be 5 m horizontally can stretch to 30–80 m, often jumping to the parallel street on the other side of the block. This is not random noise — it is systematic error concentrated in specific locations. In Cochabamba, some narrow colonial-era streets in the city centre produce this pattern reliably.

**3. Cold start / signal acquisition noise**

When the GPS receiver has not been used recently, it must re-acquire the satellite constellation before it can compute a reliable fix. During this "cold start" period (typically 15–60 seconds), the receiver may report positions that are 50–300 m off the true location. These appear as anomalous points at the very beginning of a recording session and are particularly dangerous because they occur precisely when `point_index=0` is being set — the trip's start position.

**4. Signal loss gaps (tunnels, underpasses, parking garages)**

GPS signal is lost entirely when the device is underground or under thick cover. What happens next depends on the device:
- *Gap*: the receiver stops reporting fixes until signal returns. Valhalla handles these as interpolated segments.
- *Phantom drift*: some receivers continue reporting fixes extrapolated from the last known velocity. These phantom points are spatially coherent (they look like the bus kept moving in a straight line) but are wrong. They pass Valhalla's match-score check reasonably well if the road happens to continue in that direction, but they increase the `mean_snap_distance`.

**5. GDOP spikes from satellite geometry changes**

GPS satellites move continuously. Every few minutes, a satellite rises or sets on the horizon, changing the geometric configuration visible to the receiver. Occasionally this transition causes a brief spike in position error — a single point 20–80 m off the true position — even in open sky. These appear as isolated outlier points and are classified as `"unmatched"` by Valhalla when the error is large enough.

**6. Device-specific filtering and sampling behaviour**

Different phones and operating systems handle GPS very differently:

- *iOS course smoothing*: Apple applies a low-pass filter to GPS output. This reduces noise but causes the reported position to lag slightly behind the true position when turning. Corners appear "cut" in the raw trace.
- *Android variability*: Android GPS sampling rates range from 1 Hz (power-saving mode) to 5 Hz or more. Many budget Android devices common in Bolivia apply aggressive position smoothing that introduces a different type of systematic error.
- *Stationary noise*: When the bus is stopped at a red light or terminal, GPS accuracy does not improve. The device continues reporting positions within a cloud of 5–15 m around the true position, producing a dense "puff" of points that inflate the local point count without adding information.

**7. Speed-dependent accuracy**

GPS receivers use Doppler shift of satellite signals to estimate velocity. When the device is moving, this provides an independent check on position changes that improves accuracy. When the device is stationary, this check is unavailable, and position accuracy degrades slightly. A bus that stops frequently will have marginally worse GPS accuracy at stops than while moving.

---

### What Valhalla is

[Valhalla](https://github.com/valhalla/valhalla) is an open-source routing engine that works on OpenStreetMap data. It is self-hosted — the project runs its own Valhalla instance. The specific feature used here is **Meili**, Valhalla's map-matching module, which implements a Hidden Markov Model (HMM) to snap noisy GPS traces onto the road network.

### Why map-matching instead of raw GPS

Given the noise types above, a naive "snap each GPS point to the nearest road" approach has three fundamental failures:

1. **Multipath and atmospheric noise** cause individual points to land on the wrong road. Nearest-road snapping picks the wrong segment each time, and there is no way to recover from a bad snap.
2. **Variable density** means some parts of the route have many points and others have few, making the raw point cloud unsuitable as input to DBSCAN.
3. **Ambiguous turns and intersections**: at a junction, the nearest road segment may be the one the bus did not take. Snapping greedily makes systematically wrong choices at every intersection.

### How the HMM algorithm works

A Hidden Markov Model (HMM) is a probabilistic model for sequences. It has:
- **Hidden states** — the true situation at each timestep, which we cannot observe directly
- **Observations** — what we can observe, which are noisy signals from the hidden state
- **Emission probabilities** — for each hidden state, the probability of producing each possible observation
- **Transition probabilities** — for each pair of consecutive states, the probability of moving from one to the other

For GPS map-matching, these are:
- **Hidden states** = the road segment the vehicle is actually on at each GPS timestep
- **Observations** = the GPS coordinates reported by the phone

**Emission probability** — For each GPS point _i_ and each nearby road segment _r_ (within `search_radius`), the emission probability models how likely it is that the vehicle on road _r_ produced the observed GPS reading:

```
P(GPS_i | road_r) ∝ exp( -d² / (2σ²) )
```

where `d` is the perpendicular snap distance from GPS_i to road_r, and `σ = gps_accuracy` (20 m). This is a Gaussian: a GPS point 5 m from the road has high emission probability; one 60 m away has very low probability. The 20 m standard deviation was chosen as a conservative estimate appropriate for urban GPS on consumer smartphones.

**Transition probability** — For each pair of consecutive road segments (_r_ at step _i_, _r'_ at step _i+1_), the transition probability models whether moving from _r_ to _r'_ is consistent with observed GPS movement. Meili uses the formulation from [Newson & Krumm 2009]:

```
P(r → r') ∝ exp( -|d_road(r, r') - d_gps(i, i+1)| / β )
```

where:
- `d_road(r, r')` = shortest path distance on the road network between the two segments
- `d_gps(i, i+1)` = straight-line distance between consecutive GPS points
- `β` = a scale factor

The intuition: if the GPS moved 100 m and the road distance between the two candidate segments is also ~100 m, the transition is plausible. If the road requires a 2 km detour to connect the two segments, the transition probability is very low — the algorithm will not "teleport" across the map. The `costing = "bus"` model sets transition probability to zero for road segments buses cannot legally use (pedestrian paths, wrong-direction one-way streets, etc.).

**The Viterbi algorithm** — Given all emissions and transitions, the Viterbi algorithm finds the single most-likely sequence of road segments for the entire GPS trace. It avoids evaluating all possible sequences (which would be exponential) through dynamic programming:

1. For GPS point 0: for each candidate road segment _r_, compute `score[0][r] = emission(r, GPS_0)`.
2. For each subsequent GPS point _i_: for each candidate road segment _r_, compute:

   ```
   score[i][r] = emission(r, GPS_i) × max over all r' { score[i-1][r'] × transition(r', r) }
   ```

   Store a back-pointer recording which _r'_ gave the maximum.

3. After the last GPS point: the best final segment is `argmax_r score[n][r]`.
4. Follow back-pointers from the best final segment to recover the full sequence.

The critical advantage over greedy snapping: at step _i_, the score for being on road _r_ depends on the best way to have arrived at _r_ from all possible previous states. A GPS point that appears to be on road A might receive a higher score for road B if road B is more topologically consistent with where the vehicle came from and where it is going next. The algorithm considers the entire trace simultaneously, not just one point at a time.

### The Valhalla API call

The endpoint used is `POST /trace_attributes` with `shape_match: "map_snap"`.

**Request body parameters:**

| Parameter | Value | Notes |
|---|---|---|
| `shape` | array of `{lat, lon, time}` | One entry per `TripSessionPoint`, ordered by timestamp |
| `costing` | `"bus"` | Valhalla routing profile. `bus` allows roads that buses can use (excludes pedestrian paths, footways, bike lanes). Using `auto` would allow all roads but also permit turns that buses cannot make. |
| `shape_match` | `"map_snap"` | Forces Meili to snap each GPS point to a road, rather than `"trace_route"` which would produce a turn-by-turn itinerary |
| `trace_options.search_radius` | `60` (metres) | The radius around each GPS point in which Valhalla searches for candidate road segments. 60 m is generous enough to handle poor urban GPS signal between buildings. Lower values increase precision but cause more unmatched points. |
| `trace_options.gps_accuracy` | `20` (metres) | The expected GPS horizontal accuracy. Used to set the emission probability standard deviation in the HMM. If the device reports `horizontal_accuracy`, a more sophisticated implementation would use it per-point; here we use a fixed value. |

### What Valhalla returns

The response includes two things:

**`shape`** — The full road geometry of the matched path, encoded as polyline6. This is the dense road edge geometry interpolated along OSM ways. It is decoded by `_decode_polyline6()`, which reverses Google's polyline encoding at 1e-6 precision instead of the usual 1e-5.

**`matched_points`** — One entry per input GPS point, each with:
- `lat`, `lon` — the GPS point snapped to the road
- `type` — `"matched"`, `"interpolated"`, or `"unmatched"`
  - `"matched"` — the point was successfully snapped to the HMM sequence
  - `"interpolated"` — the point was between two matched segments (small gap filled in)
  - `"unmatched"` — Valhalla could not find a plausible road for this point; usually means the GPS was too far off-road or the road is missing from OSM
- `distance_from_trace_point` — the distance in metres from the original GPS point to the snapped position (snap distance)

### Why we use matched_points geometry, not the shape geometry

The `shape` field gives the full road topology between the start and end — it follows every turn, intersection, and curve in the OSM ways. However, when two adjacent GPS points are on different sides of a turn restriction or a one-way segment, Valhalla may route through a detour that the bus did not actually take. The `matched_points` positions, by contrast, are just the snapped positions of the original GPS inputs — they cannot introduce detours. This is the geometry stored in `Trip.computed_path`.

The trade-off: `matched_points` geometry is less smooth than the road-following `shape`, and has the same variable density as the original GPS. This is why the next step (resampling) is needed.

### Quality metrics computed

**`match_score`** = number of `"matched"` points / total points. Range 0–1. A score of 1.0 means every GPS point found a road. A low score (< 0.5) usually means the route left mapped roads, OSM coverage is poor, or the GPS signal was bad throughout.

Note: `"interpolated"` points are not counted as matched. They are accepted into the geometry (they fill small gaps) but they contribute 0 to the score, as their position is inferred, not confirmed.

**`mean_snap_distance`** = mean `distance_from_trace_point` across all matched points, in metres. Stored in `Trip.frechet_distance` (naming is historical). Typical values for urban GPS are 3–15 m. Values above 30 m suggest systematic GPS drift or OSM road position errors.

### What is stored

A `Trip` row is created for each successfully matched session:

| Field | Value |
|---|---|
| `session_id` | FK to the source `TripSession` |
| `line_id` | Copied from the session |
| `status` | `TripStatus.CLEAN` (all map-matched trips start as clean) |
| `match_score` | Computed quality metric (0–1) |
| `frechet_distance` | Mean snap distance in metres |
| `computed_path` | PostGIS LINESTRING built from `matched_points` positions (excluding unmatched) |
| `processed_at` | Timestamp of the map-matching run |

A `TripPoint` row is created for each non-unmatched GPS point:

| Field | Value |
|---|---|
| `trip_id` | FK to the `Trip` |
| `point_index` | Sequential integer (0, 1, 2, ...) counting only matched/interpolated points |
| `timestamp` | Original GPS timestamp from the device |
| `latitude` / `longitude` | Snapped road position from `matched_points` |
| `point` | PostGIS POINT duplicate |

Unmatched points are discarded entirely — they do not appear in `trip_points`.

### Processing status transitions

During the match attempt, `TripSession.processing_status` is set:
- `RAW → PROCESSING` before the Valhalla call (at `db.flush()`, not committed)
- `PROCESSING → PROCESSED` after successful commit
- `PROCESSING → FAILED` if Valhalla returns an HTTP error

The `FAILED` state means the session is permanently excluded from further pipeline runs (the batch query filters for `RAW` only).

### Batch entry point

`match_line(db, line_id)` queries all `TripSession` rows with `processing_status=RAW` and `status=COMPLETED` for a given line, and calls `match_session()` on each. Sessions that raise `ValueError` or `RuntimeError` are caught, added to the `failed` list, and do not interrupt the batch.

---

## Step 3 — Resampling to Uniform Distance Intervals

**File:** `packages/geodata/src/geodata/resample.py`

### Why resample

After map-matching, `TripPoint`s are at the same irregular spacing as the original GPS (variable GPS sampling rate, variable bus speed). Two different trips on the same route might have very different point counts per kilometre. DBSCAN in step 5 works on a pooled point cloud, and if trips have unequal density, faster-sampled trips would dominate the cluster centres. Resampling normalises all trips to the same spatial resolution.

Additionally, uniform spacing gives each cluster a consistent vote weight: one trip = one point per interval, regardless of how fast the bus was moving.

### The algorithm

**Input:** a list of `TripPoint`s (sorted by timestamp)
**Parameter:** `interval_meters` (e.g. 20.0)
**Output:** a list of `ResampledPoint`s with uniform spacing

**Step 1 — Compute cumulative arc-length.** For each consecutive pair of points, compute the great-circle distance with Haversine and add it to a running sum. This gives `cum[i]` = total path length from the start up to point `i`.

**Step 2 — Build a uniform distance grid.** Starting at 0, add `interval_meters` repeatedly until the total path length is reached. The epsilon `1e-6` in the stop condition (`d <= total + 1e-6`) ensures the last grid point is included even when floating-point arithmetic lands just short of `total`.

**Step 3 — Linearly interpolate.** For each target distance on the grid, find the two surrounding original points (the O(n) single-pass cursor `j` avoids an O(n²) search). Compute the fractional position between them:

```
frac = (target_d - cum[j]) / (cum[j+1] - cum[j])
```

The epsilon `1e-9` in the denominator guards against degenerate zero-length segments (two identical consecutive points). `frac` is clamped to [0, 1].

Latitude, longitude, and Unix timestamp are all interpolated with the same `frac`. This means the `timestamp` field on each `ResampledTripPoint` is an estimate, not a real observation — it preserves temporal density for potential future analysis but should not be treated as precise.

### The Haversine distance formula

Used for all distance calculations in the pipeline (in `geo_math.py`):

```
a = sin²(Δlat/2) + cos(lat1) * cos(lat2) * sin²(Δlon/2)
c = 2 * atan2(√a, √(1-a))
distance = R * c
```

Where `R = 6,371,000 m` (mean Earth radius). This is the true great-circle distance on a sphere. For urban distances (< 50 km) the error from using a sphere instead of the WGS-84 ellipsoid is under 0.3%.

### Idempotency

Before running resampling, the code checks for an existing `ResampledTrip` at the same `(trip_id, interval_meters)`. If one exists, it is returned as-is without recomputation. This means the batch command can be re-run safely — already-resampled trips are skipped in O(1).

### The `match_score` stored on `ResampledTrip`

This is a source of potential confusion. `ResampledTrip.match_score` does **not** store the trip's own match quality. It stores the **minimum score filter threshold** that was in effect when the batch was run. For example, if you ran "batch resample" with min_score=0.7, every resulting `ResampledTrip` gets `match_score=0.7`. This is used later to reconstruct which batch a resampled trip belongs to when querying by (interval, score) pair in the notebook dropdown and in validation/clustering steps.

Trips resampled without a score filter (min_score=0.0, the default) get `match_score=0.0` stored.

### What is stored

A `ResampledTrip` row:

| Field | Value |
|---|---|
| `trip_id` | FK to the source `Trip` |
| `interval_meters` | The resampling interval used |
| `match_score` | The batch filter threshold (not the trip quality) |
| `point_count` | Number of output points |

One `ResampledTripPoint` per output point:

| Field | Value |
|---|---|
| `resampled_trip_id` | FK to `ResampledTrip` |
| `point_index` | Sequential integer 0, 1, 2, ... — critically, this is the along-route index used for cluster ordering in step 5 |
| `timestamp` | Interpolated UTC datetime |
| `latitude` / `longitude` | Interpolated WGS-84 coordinates |
| `point` | PostGIS POINT duplicate |

### Batch entry point

`resample_line(db, line_id, interval_meters, min_match_score)` iterates over all `Trip`s for the line and calls `resample_trip()` on each one that meets the score threshold. Trips below the threshold are added to `result.skipped`; they are not deleted or modified.

---

## Step 4 — Direction Validation

**File:** `packages/geodata/src/geodata/validate.py`

### Why direction must be checked before DBSCAN

DBSCAN clusters by spatial density. On a bidirectional line (bus goes A→B and B→A on the same road), all trips pass through the same physical locations regardless of direction. The clustering step will correctly identify the road corridor as a high-density region. However, the cluster-ordering step in step 5 relies on the `point_index` field increasing monotonically along the route. A trip going B→A will have `point_index=0` near B and `point_index=N` near A. A trip going A→B will have `point_index=0` near A. If both are pooled, the mean `point_index` per cluster will be approximately the same everywhere (cancelling out), making the ordering undefined. The result would be a random or zigzag route.

This step detects which trips are going in each direction so the caller can split them before clustering.

### Direction vector computation

For each resampled trip, only the **first and last** `ResampledTripPoint` are used (not all points, not a centroid of all points). The reason: intermediate detours (e.g. a bus looping around a terminus, waiting at a stop on the wrong side of the road) can distort a centroid-based direction estimate. The start→end displacement vector captures the net travel direction and is robust to these local detours.

The vector is computed in a **flat-earth approximation**:
```
east  = (lon_end - lon_start) × 111,320 × cos(mean_lat_rad)
north = (lat_end - lat_start) × 111,320
```

The constant 111,320 converts degrees of latitude to metres (one degree of latitude ≈ 111.32 km at all latitudes). The `cos(mean_lat)` factor corrects longitude degrees to metres — longitude degrees are shorter at higher latitudes. The mean of start and end latitudes is used as the reference, which is accurate for trip lengths up to tens of kilometres.

The vector is normalised to unit length. If the crow-fly distance between start and end is less than `min_distance_m` (default: 50 m), the trip is classified as `UNKNOWN` — it is too short, or a near-circular loop, to determine direction from start→end alone.

### Canonical direction resolution

Given a list of unit direction vectors, we need one canonical "forward" direction to compare against. The challenge is the 180° ambiguity: for a trip going A→B, the unit vector points one way; for a trip going B→A on the same road, it points the opposite way. Both are valid recordings of the same route.

The algorithm:
1. Take the first trip's vector as an initial reference.
2. Count how many of the remaining vectors have a positive dot product with it (i.e. point roughly the same way) vs negative (point the other way).
3. If the minority agreed with the first vector, flip the reference 180°. This ensures the reference points in the majority direction.
4. Align all vectors to the reference (flip those with a negative dot product against it).
5. Return the normalised mean of all aligned vectors.

The result is the mean direction of the dominant group. If exactly half the trips go each way (perfectly balanced bidirectional batch), the mean of aligned vectors degenerates to near-zero magnitude, and the function returns `None` — this is the one edge case where canonical direction cannot be determined.

### Classification

For each trip, the dot product between its unit vector and the canonical forward vector gives a score in [-1, 1]:
- `+1.0` — perfectly aligned with the dominant direction
- `0.0` — perpendicular (ambiguous)
- `-1.0` — exactly opposite

The threshold `reverse_threshold = -0.1` (default) means: classify as `REVERSE` only if the dot product is strictly below -0.1. The 0.1 deadband (~6°) prevents L-shaped partial trips or slight angle mismatches from being misclassified as reverse. A trip covering only one corner of the route might have a start→end vector that is perpendicular to the main axis, yielding a dot score near 0; the deadband keeps it in `FORWARD`.

The `dot_score` is stored on `TripDirectionResult` and is useful in the notebook to identify low-confidence classifications (e.g. `|dot_score| < 0.5`) that might need manual review.

### Output

`DirectionValidationResult` contains:
- `trips: list[TripDirectionResult]` — one per trip, with `trip_id`, `resampled_trip_id`, `direction`, `dot_score`
- `n_forward`, `n_reverse`, `n_unknown` — counts
- `is_mixed: bool` — `True` when both `FORWARD` and `REVERSE` trips are present
- `.forward_trips` / `.reverse_trips` — convenience properties returning filtered lists

When `is_mixed=True`, the caller should run the clustering step twice: once with forward trip IDs and once with reverse trip IDs, producing two `RouteEstimation`s.

---

## Step 5 — DBSCAN Clustering

**File:** `packages/geodata/src/geodata/cluster.py`
**Library:** `scikit-learn` (DBSCAN), `numpy`

### Why DBSCAN

Several clustering algorithms could be used here. DBSCAN was chosen because:

1. **No need to specify the number of clusters.** We do not know in advance how many waypoints a route has. K-means requires k; DBSCAN requires only a distance threshold.
2. **Noise handling.** Points that do not belong to any cluster (outlier GPS, erroneous sessions that made it through map-matching) are labelled as noise (label -1) and excluded from the output. K-means assigns every point to a cluster, including outliers.
3. **Arbitrary shape.** Transit routes are curved. DBSCAN handles non-convex clusters naturally.
4. **Physical interpretation of `eps`.** The parameter means "two points are neighbours if they are within X metres of each other" — directly interpretable in geographic terms.

The alternative was HDBSCAN (hierarchical DBSCAN, available in scikit-learn ≥ 1.3), which handles variable-density clusters better. It was not used because the resampling step already normalises density, so a single `eps` should work uniformly along the route.

### How the DBSCAN algorithm works

DBSCAN (Density-Based Spatial Clustering of Applications with Noise) groups points by local density. It introduces three categories:

**Core point** — a point _p_ is a core point if at least `min_samples` points (including _p_ itself) lie within distance `eps` of _p_. Core points anchor clusters.

**Border point** — a point that is not a core point itself (it has fewer than `min_samples` neighbours) but falls within `eps` of at least one core point. It gets assigned to that core point's cluster but does not expand it.

**Noise point** — any point that is neither a core point nor within `eps` of any core point. Labelled -1 and excluded from all clusters.

**The algorithm**, informally:

```
For each unvisited point p:
    Mark p as visited.
    Find all points within eps of p  →  neighbourhood N(p).
    If |N(p)| < min_samples:
        Label p as noise (may be promoted later to a border point).
    Else:
        Start a new cluster C, add p to it.
        Let the "frontier" = N(p).
        While the frontier is not empty:
            Take a point q from the frontier.
            If q is unvisited:
                Mark q as visited.
                Find N(q).
                If |N(q)| >= min_samples:
                    Add all of N(q) to the frontier  (expand the cluster).
            If q is not yet in any cluster:
                Add q to C.
```

The cluster grows outward from the seed core point by absorbing all density-reachable points. Two points are in the same cluster if and only if there is a chain of core points connecting them, each within `eps` of the next.

**Time complexity** — The naive implementation is O(n²) because computing N(p) for each point requires comparing it against all other points. With a spatial index (BallTree in our case), neighbourhood queries take O(log n) on average, reducing the full algorithm to O(n log n). For 5,000 points this is essentially instantaneous.

**Why density means "the route is here" in our context**

Each position along the route is visited by every trip. With 20 trips resampled at 20 m and `eps = 30 m`, a location on the route has approximately 20 points within 30 m of each other (the post-match-matching positional variance is typically under 10 m). Every one of those 20 points is a core point with 19 neighbours inside `eps`. The entire cluster grows to encompass all 20 points and gets one centroid — one waypoint on the reconstructed route.

A location that appears in only 2 trips has at most 2 points within 30 m. With `min_samples = max(2, 20//3) = 6`, those 2 points cannot be core points. They are noise — excluded. This is how DBSCAN automatically filters GPS artefacts, one-off detours, and sparse partial-trip sections: they simply do not have enough points to form a cluster.

**Border points in our context**

Between two adjacent clusters (two consecutive waypoints 20 m apart), the cluster boundaries overlap slightly because `eps (30 m) > interval (20 m)`. Points near the boundary may fall within `eps` of core points in both clusters. DBSCAN assigns them to whichever cluster's core point is encountered first during the sweep, which is non-deterministic. This does not affect the result meaningfully because the centroid of each cluster is computed from all its member points, and the boundary points are at approximately the same distance from both centroids — their assignment has negligible influence on centroid position.

### Point cloud construction

All `ResampledTripPoint` rows for the selected resampled trips are loaded and assembled into a numpy array with four columns per row:

```
[latitude, longitude, point_index, trip_index]
```

- `latitude`, `longitude` — the coordinates DBSCAN will cluster on
- `point_index` — the along-route index (0 = trip start, N = trip end) — used for cluster ordering after DBSCAN, not for clustering itself
- `trip_index` — a 0-based integer identifying which resampled trip the point came from — used to count distinct trips per cluster for confidence computation

For a typical run: 20 trips × (route_length / interval_meters) points each. E.g. 20 trips on a 5 km route at 20 m spacing = 20 × 250 = 5,000 points.

### DBSCAN configuration

**`metric = "haversine"`** — DBSCAN computes all pairwise distances using the haversine formula. This works directly on WGS-84 coordinates without any projection. Scikit-learn's haversine metric requires input in **radians**, so coordinates are converted with `np.radians(coords)` before the call. The resulting clusters are defined by great-circle distance.

**`algorithm = "ball_tree"`** — The spatial indexing algorithm. BallTree supports haversine distance natively and is efficient for geographic point clouds. The alternative `kd_tree` does not support haversine; `brute` would work but is O(n²).

**`eps`** — The neighbourhood radius. Passed in metres by the caller (`eps_meters`, default 30 m); converted to radians internally:
```
eps_rad = eps_meters / 6_371_000
```
The choice of 30 m for 20 m resampling is intentional: it is 1.5× the resampling interval, meaning two points from different trips at the same location will always be within `eps` of each other (they differ by at most the GPS + snap distance, typically < 10 m after map-matching), while two points on parallel roads 50+ m apart will not be. For dense urban grids where parallel roads are 30–40 m apart, `eps` should be reduced to ~15 m.

**`min_samples`** — The core-point threshold. A point is a core point (and can anchor a cluster) only if at least `min_samples` other points are within `eps` of it. Default: `max(2, n_trips // 3)`. With 9 trips, this gives `min_samples=3` — a location must appear in at least 3 trips to be considered part of the route. This filters out GPS artefacts that appear in only one or two trips. Increasing `min_samples` raises the confidence bar but can cause thin-coverage route ends to be labelled as noise.

### Post-DBSCAN: per-cluster statistics

For each cluster label (all labels except -1):

**Centroid** = arithmetic mean of the `latitude` and `longitude` of all member points. This is the arithmetic mean in degree-space, which introduces a tiny spherical distortion for large clusters, but for clusters of radius < 50 m this is negligible (< 0.1 m error).

**`mean_point_index`** = arithmetic mean of the `point_index` values of all member points. This is the key to ordering clusters along the route.

**`distinct_trips`** = count of unique trip indices in the cluster. A cluster with high `distinct_trips` (close to `n_trips`) means nearly every trip passes through this location — high confidence. A cluster with low `distinct_trips` means only a few trips cover this part of the route — low confidence, possibly a partial-trip section or a GPS artefact.

### Cluster ordering by mean_point_index

After DBSCAN, the cluster labels are unordered integers assigned by the algorithm's visit order (not geographic or temporal). To reconstruct a sequential route, clusters must be sorted into along-route order.

The ordering key is `mean_point_index`. This works because:
1. All trips were resampled at the same `interval_meters` in the same direction.
2. `point_index=0` on every trip is the trip's geographic start; `point_index=N` is its end.
3. A cluster near the route start will have points from many trips all with low `point_index` values → low `mean_point_index`.
4. A cluster near the route end will have points with high `point_index` values → high `mean_point_index`.
5. Sorting by `mean_point_index` gives the correct geographic sequence without any nearest-neighbour search or PCA.

This approach fails only if direction validation was skipped and the batch contains reverse trips — their `point_index` values run backwards relative to forward trips, making `mean_point_index` uninformative. This is why direction validation must precede clustering.

For partial trips (trips that cover only a segment of the full route), the `point_index` values in the covered section still reflect the correct relative position because resampling starts from 0 at the trip's own start point. However, if all partial trips start near the same geographic point, the cluster ordering will still be correct. Problems arise only if some trips start mid-route while others start at the terminus — in that case, the partial trips' `point_index` series is offset from the full trips', and `mean_point_index` may not be monotonic for clusters in the shared section. This is an open limitation.

### Segment construction and confidence

After sorting, consecutive cluster pairs `(cluster[i], cluster[i+1])` define route segments. Each segment becomes a `RouteSegment` row:

- **`path`** — a PostGIS LINESTRING from `(centroid_lon[i], centroid_lat[i])` to `(centroid_lon[i+1], centroid_lat[i+1])`. Note the coordinate order: Shapely and PostGIS use (longitude, latitude), which is (x, y).
- **`sequence`** — integer 0, 1, 2, ... reflecting position along the route
- **`confidence`** — `min(distinct_trips[i], distinct_trips[i+1]) / n_trips`. The `min` means a segment is only as confident as its least-observed endpoint. If the end of the route is covered by only 3 out of 10 trips, all segments involving those end clusters will have confidence ≤ 0.3, even if the rest of the route has full coverage.
- **`status`** — `SegmentStatus.PENDING` (awaiting user votes)
- **`votes_for`**, **`votes_against`** — initialised to 0

For `N` clusters there are `N-1` segments.

### Versioning

Every call to `cluster_route()` marks all existing non-superseded `RouteEstimation`s for the same line as `EstimationStatus.SUPERSEDED` before writing the new one. The new estimation gets `version = max_existing_version + 1`. This means:
- Re-running the pipeline with different parameters always produces a new estimation.
- Previous estimations are preserved in the database (not deleted) — their segments and votes remain accessible for audit or rollback.
- Only the latest non-superseded estimation is considered "active" from the application's perspective.

The `status` of the new estimation starts as `EstimationStatus.PENDING`. It can be manually promoted to `EstimationStatus.CONFIRMED` after user voting validates the result.

---

## Observability

All five pipeline steps are instrumented with **OpenTelemetry** traces via the `tracer` from `geodata.telemetry`. Each function opens a span with relevant attributes:

| Function | Span name | Key attributes |
|---|---|---|
| `trace_match` | `valhalla.trace_attributes` | `valhalla.costing`, `valhalla.num_points`, `match.score`, `match.mean_snap_distance` |
| `match_session` | `match_session` | `session_id`, `points.raw`, `points.matched`, `trip.id` |
| `match_line` | `match_line` | `line_id`, `sessions.total`, `sessions.matched`, `sessions.failed` |
| `resample_trip` | `resample_trip` | `trip_id`, `interval_meters`, `points.input`, `points.output`, `was_existing` |
| `resample_line` | `resample_line` | `line_id`, `interval_meters`, `min_match_score`, `trips.resampled`, `trips.skipped`, `trips.failed` |
| `validate_trip_directions` | `validate_trip_directions` | `line_id`, `interval_meters`, `trips.forward`, `trips.reverse`, `trips.unknown`, `trips.is_mixed` |
| `cluster_route` | `cluster_route` | `line_id`, `interval_meters`, `eps_meters`, `dbscan.n_clusters`, `dbscan.n_noise`, `segments.saved` |

---

## Library Inventory

| Library | Version | Purpose |
|---|---|---|
| `valhalla` | self-hosted service | Map-matching (HMM) via HTTP |
| `httpx` | ≥ 0.28.0 | HTTP client for Valhalla calls |
| `sqlalchemy` | ≥ 2.0.48 | ORM and query building |
| `sqlmodel` | bundled with `database` package | SQLModel models (SQLAlchemy + Pydantic) |
| `geoalchemy2` | ≥ 0.18.4 | PostGIS geometry column types and `from_shape` / `to_shape` converters |
| `shapely` | ≥ 2.0.0 | In-memory geometry construction (`Point`, `LineString`) |
| `numpy` | ≥ 2.4.2 | Array operations for DBSCAN input and per-cluster statistics |
| `scikit-learn` | ≥ 1.8.0 | `DBSCAN` implementation with haversine metric and BallTree indexing |
| `opentelemetry-api` | ≥ 1.20.0 | Distributed tracing instrumentation |
| `psycopg2-binary` | ≥ 2.9.11 | PostgreSQL driver (underlying SQLAlchemy connection) |

---

## Parameter Reference

| Parameter | Location | Default | Effect |
|---|---|---|---|
| `costing` | `trace_match` | `"bus"` | Valhalla routing profile — controls which roads are considered valid |
| `search_radius` | `trace_match` | `60` m | HMM candidate search radius per GPS point |
| `gps_accuracy` | `trace_match` | `20` m | HMM emission probability standard deviation |
| `interval_meters` | `resample_points` | caller-set | Spacing between output resampled points |
| `min_match_score` | `resample_line` | `0.0` | Minimum trip quality to include in resampling |
| `min_distance_m` | `validate_trip_directions` | `50` m | Minimum start→end distance to classify direction |
| `reverse_threshold` | `validate_trip_directions` | `-0.1` | Dot product below which a trip is labelled REVERSE |
| `eps_meters` | `cluster_route` | `30` m | DBSCAN neighbourhood radius |
| `min_samples` | `cluster_route` | `max(2, n_trips//3)` | DBSCAN core-point minimum neighbour count |

---

## Known Limitations

**Partial trips and `point_index` offset.** If some trips cover only part of the route (e.g. a driver joined mid-route and recorded from km 3 to km 8 of a 10 km line), their `point_index` series starts at 0 at km 3, not at the true route start. The `mean_point_index` cluster ordering may be disturbed in the overlap region.

**Perfectly balanced bidirectional batches.** If exactly half the trips go A→B and half go B→A, `_canonical_forward()` returns `None` and all trips are classified `UNKNOWN`. The clustering step receives all trips, producing an incorrect ordering. Mitigation: always ensure at least one direction has a clear majority, or manually split the batches.

**Dense parallel roads.** If two parallel roads are closer than `eps_meters` (e.g. a one-way couplet where the two directions are 25 m apart and `eps=30`), DBSCAN will merge them into a single cluster. The centroid will land in the middle of the two roads, on a pavement or in a building. Mitigation: reduce `eps_meters`.

**Linear interpolation in lat/lon space.** The resampling step interpolates linearly in degree-space, not along geodesics. For urban distances (< 1 km between consecutive trip points) this is accurate to within millimetres. It would fail for trips with very long gaps between original points (e.g. > 50 km), which should not occur after map-matching.

**Arithmetic mean centroid on WGS-84.** Cluster centroids are computed as the arithmetic mean of lat/lon values. On a sphere this is only an approximation of the true geographic centroid, with error proportional to cluster radius. For clusters of radius < 50 m (guaranteed by `eps`), the error is under 0.5 m and is negligible.
