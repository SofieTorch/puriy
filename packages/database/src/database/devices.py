"""Device-table helpers shared across server, pipeline, and notebooks."""

from sqlalchemy import text
from sqlalchemy.orm import Session


def ensure_device(db: Session, device_id: str) -> None:
    """Ensure a row exists in `devices` for this device_id, no-op otherwise.

    Used wherever we write a row whose `device_id` is FK-constrained to
    `devices.id` but the caller may not have explicitly registered the
    device — for example the transit-lab simulators that synthesise
    voter ids and the seed scripts.
    """
    db.execute(
        text(
            "INSERT INTO devices (id, last_seen_at, created_at) "
            "VALUES (:id, NOW(), NOW()) "
            "ON CONFLICT (id) DO NOTHING"
        ),
        {"id": device_id},
    )
