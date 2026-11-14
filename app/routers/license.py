from fastapi import APIRouter, Request, HTTPException

from app.schemas.requests import OrderLicensesRequest, ActivateLicenseRequest
from app.schemas.user import LicenseToken
from app.schemas.exceptions import (
    InvalideLicenseKeyError,
    ExpiredLicenseError,
    ActivationLimitReachedError,
    ProductLicenseNotFoundError,
)
from app.services.licensing import Licensing


router = APIRouter(
    prefix='/license',
    tags=["license"]
)


@router.post('/create')
async def create(body: OrderLicensesRequest, request: Request) -> list[str]:
    """
    Create license keys for an order

    Args:
        body (OrderLicensesRequest): Order ID and the Paddle products to license
        request (Request): Default request argument

    Returns:
        list[str]: License keys, in the same order as the items

    Raises:
        HTTPException: 404 if an item references an unknown product license
    """
    licensing: Licensing = request.app.state.licensing

    #TODO: Protect access 
    # (/create can only be called from fcpxstudio webside when a product is bought)

    try:
        license_keys = licensing.create_licenses(body)
    except ProductLicenseNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown product license '{e.product_license_id}'"
        )

    return license_keys

@router.post('/activate', response_model=LicenseToken)
async def activate(body: ActivateLicenseRequest, request: Request) -> LicenseToken:
    """
    Validate and activate a license for a specific machine

    Args:
        body (ActivateLicenseRequest): License and machine informations
        request (Request): Default request argument

    Returns:
        LicenseToken: Signed token FxPlug can validate

    Raises:
        HTTPException: 404 unknown key or wrong product, 403 expired, 409 no seat left
    """
    licensing: Licensing = request.app.state.licensing

    try:
        token = licensing.activate_license(body)
    except InvalideLicenseKeyError as e:
        raise HTTPException(
            status_code=404, 
            detail=f"Invalid license key '{e.license_key}'"
        )
    except ExpiredLicenseError as e:
        raise HTTPException(
            status_code=403,
            detail=f"License expired on {e.expiration_date}"
        )
    except ActivationLimitReachedError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Activation limit reached: {e.activation_limit} / {e.activation_limit} computer registered"
        )

    return token
