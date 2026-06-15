"""Coverage metric: capped to the rider envelope, merged across ramales."""

import math

from simlab.coverage import merged_completeness, slice_by_fraction

LAT = -17.39


def line(x0, x1, n=40):
    # straight east-west line in lon degrees over ~x meters
    mlon = 111_320 * math.cos(math.radians(LAT))
    return [(x0 / mlon, LAT), (x1 / mlon, LAT)] if n == 2 else [
        ((x0 + (x1 - x0) * i / (n - 1)) / mlon, LAT) for i in range(n)
    ]


def test_slice_by_fraction_takes_a_subsegment():
    seg = slice_by_fraction(line(0, 1000), 0.0, 0.5)
    mlon = 111_320 * math.cos(math.radians(LAT))
    xs = [p[0] * mlon for p in seg]
    assert min(xs) < 5 and 480 < max(xs) < 520   # roughly [0, 500]m


def test_completeness_full_recovery():
    env = [line(0, 1000)]
    recon = [line(0, 1000)]
    comp, cells = merged_completeness(env, recon, LAT)
    assert comp == 1.0 and cells > 0


def test_completeness_half_recovery():
    env = [line(0, 1000)]
    recon = [line(0, 500)]            # only first half reconstructed
    comp, _ = merged_completeness(env, recon, LAT)
    assert 0.4 < comp < 0.6


def test_completeness_caps_to_envelope_not_full_route():
    # Envelope is only the first 80% (rider window); reconstruction covers
    # exactly that → completeness 1.0 even though 20% of the line is unbuilt.
    env = [slice_by_fraction(line(0, 1000), 0.0, 0.8)]
    recon = [slice_by_fraction(line(0, 1000), 0.0, 0.8)]
    comp, _ = merged_completeness(env, recon, LAT)
    assert comp == 1.0


def test_shared_trunk_counted_once():
    # Two ramales sharing the [0,500] trunk; reconstruction covers the union.
    # Merged completeness must be 1.0 (trunk not double-counted).
    env = [line(0, 1000), line(0, 700)]   # overlap on [0,700]
    recon = [line(0, 1000)]
    comp, _ = merged_completeness(env, recon, LAT)
    assert comp == 1.0
