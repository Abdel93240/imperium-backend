from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUserDep, SessionDep
from app.models.auth import Device
from app.models.enums import DeviceStatus
from app.schemas.devices import DeviceRegisterRequest, DeviceResponse

router = APIRouter()


@router.post("/register", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def register_device(
    payload: DeviceRegisterRequest,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> Device:
    device = Device(
        user_id=current_user.id,
        device_label=payload.device_label,
        device_fingerprint=payload.device_fingerprint,
        platform=payload.platform,
        status=DeviceStatus.trusted,
        trusted_at=datetime.now(UTC),
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.get("", response_model=list[DeviceResponse])
def list_devices(current_user: CurrentUserDep, db: SessionDep) -> list[Device]:
    return list(
        db.scalars(
            select(Device).where(Device.user_id == current_user.id).order_by(Device.created_at.asc())
        )
    )


@router.post("/{device_id}/revoke", response_model=DeviceResponse)
def revoke_device(device_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> Device:
    device = db.scalar(select(Device).where(Device.id == device_id, Device.user_id == current_user.id))
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found.")

    device.status = DeviceStatus.revoked
    device.revoked_at = datetime.now(UTC)
    db.commit()
    db.refresh(device)
    return device
