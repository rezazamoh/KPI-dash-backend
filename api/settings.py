from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database.crud import (
    _UNSET,
    get_app_settings,
    update_app_settings,
)


class DurationWindow(BaseModel):
    min: float | None = Field(default=None, ge=0)
    max: float | None = Field(default=None, gt=0)


class SettingsUpdate(BaseModel):
    duration_windows: list[DurationWindow] | None = None
    use_duration_windows: bool | None = None
    patchset_windows: list[DurationWindow] | None = None
    use_patchset_windows: bool | None = None


router = APIRouter(prefix="/api/settings", tags=["Settings"])


def _validate_windows(
    windows: list[DurationWindow] | None,
    setting_name: str,
):
    if windows is None:
        return None

    if not windows:
        raise HTTPException(
            status_code=422,
            detail=f"{setting_name} must contain at least one window or be null.",
        )

    normalized = [window.dict() for window in windows]

    if normalized[0]["min"] is not None and normalized[0]["min"] != 0:
        raise HTTPException(
            status_code=422,
            detail=f"The first {setting_name} min must be 0 or null.",
        )

    for index, window in enumerate(normalized):
        minimum = window["min"]
        maximum = window["max"]

        if minimum is None and index != 0:
            raise HTTPException(
                status_code=422,
                detail=f"Only the first {setting_name} window may have min set to null.",
            )

        if maximum is not None and minimum is not None and minimum >= maximum:
            raise HTTPException(
                status_code=422,
                detail=f"Window {index} must have min less than max.",
            )

        if maximum is None and index != len(normalized) - 1:
            raise HTTPException(
                status_code=422,
                detail=f"Only the final {setting_name} window may have max set to null.",
            )

        if index and (
            minimum is None
            or normalized[index - 1]["max"] is None
            or minimum != normalized[index - 1]["max"]
        ):
            raise HTTPException(
                status_code=422,
                detail=f"{setting_name} must be contiguous and must not overlap.",
            )

    return normalized


@router.get("")
def get_settings():
    return get_app_settings()


@router.patch("")
def patch_settings(data: SettingsUpdate):
    has_duration_windows = "duration_windows" in data.__fields_set__
    has_patchset_windows = "patchset_windows" in data.__fields_set__
    duration_windows = _validate_windows(data.duration_windows, "duration_windows")
    patchset_windows = _validate_windows(data.patchset_windows, "patchset_windows")

    if not has_duration_windows:
        duration_windows = None

    if not has_patchset_windows:
        patchset_windows = None

    return update_app_settings(
        duration_windows=(
            duration_windows
            if has_duration_windows
            else _UNSET
        ),
        use_duration_windows=data.use_duration_windows,
        patchset_windows=(
            patchset_windows
            if has_patchset_windows
            else _UNSET
        ),
        use_patchset_windows=data.use_patchset_windows,
    )