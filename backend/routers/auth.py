from fastapi import APIRouter

from helios_common.auth import create_access_token
from schemas import TokenRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse)
async def issue_token(body: TokenRequest) -> TokenResponse:
    token = create_access_token(body.analyst_id)
    return TokenResponse(access_token=token)
