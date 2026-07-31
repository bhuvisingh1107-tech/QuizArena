"""Administrator authentication routes (API_SPEC.md §7)."""

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.api.deps import (
    AuthServiceDep,
    CurrentAdmin,
    RequestContextDep,
    RequestId,
)
from app.core.rate_limit import login_rate_limiter
from app.schemas.auth import (
    AdminResponseData,
    LoginRequest,
    LoginResponseData,
    LogoutResponseData,
)
from app.schemas.common import DataResponse, Meta

router = APIRouter()


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


@router.post(
    "/login",
    response_model=DataResponse[LoginResponseData],
    status_code=status.HTTP_200_OK,
    summary="Administrator login",
)
def login(
    body: LoginRequest,
    request: Request,
    auth_service: AuthServiceDep,
    request_id: RequestId,
    context: RequestContextDep,
) -> JSONResponse:
    """Issue admin JWT; log security event (API_SPEC.md §3.1 / §7)."""
    login_rate_limiter.check(_client_key(request))
    result = auth_service.login(body.username, body.password, context=context)
    payload = DataResponse[LoginResponseData](
        data=LoginResponseData(
            access_token=result.access_token,
            expires_at=result.expires_at,
        ),
        meta=Meta(request_id=request_id),
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=payload.model_dump(mode="json", by_alias=True, exclude_none=True),
    )


@router.post(
    "/logout",
    response_model=DataResponse[LogoutResponseData],
    status_code=status.HTTP_200_OK,
    summary="Administrator logout",
)
def logout(
    admin: CurrentAdmin,
    auth_service: AuthServiceDep,
    request_id: RequestId,
    context: RequestContextDep,
) -> JSONResponse:
    """Log security event; client discards token (API_SPEC.md §3.1 / §7)."""
    auth_service.logout(admin, context=context)
    payload = DataResponse[LogoutResponseData](
        data=LogoutResponseData(),
        meta=Meta(request_id=request_id),
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=payload.model_dump(mode="json", by_alias=True, exclude_none=True),
    )


@router.get(
    "/me",
    response_model=DataResponse[AdminResponseData],
    status_code=status.HTTP_200_OK,
    summary="Current authenticated administrator",
)
def get_current_admin_profile(
    admin: CurrentAdmin,
    request_id: RequestId,
) -> JSONResponse:
    """Return the administrator identified by the Bearer JWT.

    Not listed in API_SPEC.md §7; provided so clients and tests can resolve
    the authenticated admin identity. See implementation notes.
    """
    payload = DataResponse[AdminResponseData](
        data=AdminResponseData.model_validate(admin),
        meta=Meta(request_id=request_id),
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=payload.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
