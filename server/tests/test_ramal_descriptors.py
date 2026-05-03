"""Tests for `/routes/{route_id}/descriptors` (gap #7).

Covers the vote-on-existing-first UX endpoints:
- listing returns ordered + `voted_by_me` per device,
- create returns 409 when text dedupes against an existing descriptor,
- upvote / unvote are idempotent and keep `votes_count` consistent
  with the underlying votes table.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from geoalchemy2.shape import from_shape
from shapely.geometry import LineString
from sqlalchemy.orm import Session

from database import (
    Line,
    Route,
    RouteEdge,
    RouteSource,
    RouteStatus,
)


DEVICE_A = "test-device-abc"
DEVICE_B = "other-device-xyz"


@pytest.fixture
def route(db: Session, approved_line: Line) -> Route:
    """A single ramal Route on the approved line."""
    r = Route(
        line_id=approved_line.id,
        version=1,
        ramal_label="main",
        source=RouteSource.COMPUTED,
        status=RouteStatus.CONFIRMED,
        trip_count=5,
        fragment_index=0,
        fragment_count=1,
    )
    db.add(r)
    db.flush()
    db.add(RouteEdge(
        route_id=r.id, sequence=0, valhalla_edge_id=None, forward=True,
        path=from_shape(LineString([[-66.16, -17.39], [-66.15, -17.39]]), srid=4326),
        confidence=1.0,
    ))
    db.commit()
    db.refresh(r)
    return r


# ------------------------------------------------------------------
# create
# ------------------------------------------------------------------

def test_create_descriptor_returns_201_and_creator_voted(
    client: TestClient, route: Route,
) -> None:
    resp = client.post(
        f"/routes/{route.id}/descriptors/",
        json={"text": "lleva banderines naranjas en frente", "device_id": DEVICE_A},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["text"] == "lleva banderines naranjas en frente"
    assert body["votes_count"] == 1
    assert body["voted_by_me"] is True


def test_create_409_when_text_dedupes_case_and_whitespace_insensitive(
    client: TestClient, route: Route,
) -> None:
    """Same descriptor with different casing + whitespace → 409 with
    the existing descriptor in the body so the client can offer to
    upvote it instead."""
    first = client.post(
        f"/routes/{route.id}/descriptors/",
        json={"text": "letrero con logo de Univalle", "device_id": DEVICE_A},
    )
    assert first.status_code == 201
    existing_id = first.json()["id"]

    duplicate = client.post(
        f"/routes/{route.id}/descriptors/",
        json={"text": "  Letrero con   logo de univalle ", "device_id": DEVICE_B},
    )
    assert duplicate.status_code == 409
    detail = duplicate.json()["detail"]
    assert detail["existing"]["id"] == existing_id


def test_create_400_on_empty_normalised_text(
    client: TestClient, route: Route,
) -> None:
    resp = client.post(
        f"/routes/{route.id}/descriptors/",
        json={"text": "    ", "device_id": DEVICE_A},
    )
    assert resp.status_code == 400


def test_create_404_on_unknown_route(client: TestClient) -> None:
    resp = client.post(
        f"/routes/{uuid4()}/descriptors/",
        json={"text": "anything", "device_id": DEVICE_A},
    )
    assert resp.status_code == 404


# ------------------------------------------------------------------
# list
# ------------------------------------------------------------------

def test_list_orders_by_votes_desc_then_created_at_asc(
    client: TestClient, route: Route,
) -> None:
    """Two descriptors; vote up the second → it should now lead the list."""
    a = client.post(
        f"/routes/{route.id}/descriptors/",
        json={"text": "tiene música cumbia", "device_id": DEVICE_A},
    ).json()
    b = client.post(
        f"/routes/{route.id}/descriptors/",
        json={"text": "asientos azules", "device_id": DEVICE_A},
    ).json()
    # Upvote b from a different device.
    client.post(
        f"/routes/{route.id}/descriptors/{b['id']}/upvote",
        json={"device_id": DEVICE_B},
    )
    listed = client.get(f"/routes/{route.id}/descriptors/").json()
    assert [d["id"] for d in listed] == [b["id"], a["id"]]


def test_list_marks_voted_by_me_for_supplied_device(
    client: TestClient, route: Route,
) -> None:
    """`voted_by_me` is True only for the device passed in `?device_id=`."""
    created = client.post(
        f"/routes/{route.id}/descriptors/",
        json={"text": "logo de Univalle al frente", "device_id": DEVICE_A},
    ).json()

    # Same device sees it as voted (creator vote counts).
    listed_a = client.get(
        f"/routes/{route.id}/descriptors/", params={"device_id": DEVICE_A},
    ).json()
    assert listed_a[0]["id"] == created["id"]
    assert listed_a[0]["voted_by_me"] is True

    # Other device sees it as not-yet-voted.
    listed_b = client.get(
        f"/routes/{route.id}/descriptors/", params={"device_id": DEVICE_B},
    ).json()
    assert listed_b[0]["voted_by_me"] is False


# ------------------------------------------------------------------
# upvote / unvote
# ------------------------------------------------------------------

def test_upvote_increments_votes_count_once_per_device(
    client: TestClient, route: Route,
) -> None:
    """A device can upvote at most once; subsequent upvotes are no-ops."""
    created = client.post(
        f"/routes/{route.id}/descriptors/",
        json={"text": "señor del volante con bigote", "device_id": DEVICE_A},
    ).json()

    # Different device upvotes → 1 → 2.
    bumped = client.post(
        f"/routes/{route.id}/descriptors/{created['id']}/upvote",
        json={"device_id": DEVICE_B},
    ).json()
    assert bumped["votes_count"] == 2

    # Same device upvotes again → still 2.
    again = client.post(
        f"/routes/{route.id}/descriptors/{created['id']}/upvote",
        json={"device_id": DEVICE_B},
    ).json()
    assert again["votes_count"] == 2


def test_unvote_decrements_and_is_idempotent(
    client: TestClient, route: Route,
) -> None:
    created = client.post(
        f"/routes/{route.id}/descriptors/",
        json={"text": "color verde con franja roja", "device_id": DEVICE_A},
    ).json()
    client.post(
        f"/routes/{route.id}/descriptors/{created['id']}/upvote",
        json={"device_id": DEVICE_B},
    )

    # First unvote: 2 → 1.
    after_one = client.request(
        "DELETE",
        f"/routes/{route.id}/descriptors/{created['id']}/upvote",
        json={"device_id": DEVICE_B},
    ).json()
    assert after_one["votes_count"] == 1
    assert after_one["voted_by_me"] is False

    # Second unvote (same device, no vote left): no-op, count unchanged.
    after_two = client.request(
        "DELETE",
        f"/routes/{route.id}/descriptors/{created['id']}/upvote",
        json={"device_id": DEVICE_B},
    ).json()
    assert after_two["votes_count"] == 1


def test_upvote_404_on_descriptor_for_other_route(
    client: TestClient, db: Session, route: Route, approved_line: Line,
) -> None:
    """A descriptor's URL is route-scoped; mismatching route in the path
    gives 404 even when the descriptor_id exists elsewhere."""
    other_route = Route(
        line_id=approved_line.id, version=2, ramal_label="r2",
        source=RouteSource.COMPUTED, status=RouteStatus.CONFIRMED,
        trip_count=3, fragment_index=0, fragment_count=1,
    )
    db.add(other_route)
    db.commit()
    db.refresh(other_route)

    created = client.post(
        f"/routes/{route.id}/descriptors/",
        json={"text": "es bus mediano", "device_id": DEVICE_A},
    ).json()
    resp = client.post(
        f"/routes/{other_route.id}/descriptors/{created['id']}/upvote",
        json={"device_id": DEVICE_B},
    )
    assert resp.status_code == 404
