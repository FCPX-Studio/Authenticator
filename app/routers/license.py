from fastapi import APIRouter, Request, HTTPException
from paddle_billing.Exceptions.ApiError import ApiError
from requests import RequestException

from app.schemas.requests import PaddleTransactionCompletedEvent, ActivateLicenseRequest
from app.schemas.user import LicenseToken
from app.schemas.exceptions import (
    InvalideLicenseKeyError,
    ExpiredLicenseError,
    ActivationLimitReachedError,
    ProductLicenseNotFoundError,
)
from app.services import Licensing, Paddle


router = APIRouter(
    prefix='/license',
    tags=["license"]
)


@router.post('/create')
async def create(body: PaddleTransactionCompletedEvent, request: Request) -> list[str]:
    """
    Create license keys for an order

    Args:
        body (PaddleTransactionCompletedEvent): Paddle transaction.completed body
        request (Request): Default request argument

    Returns:
        list[str]: License keys, in the same order as the items

    Raises:
        HTTPException: 401 for bad body signature
        HTTPException: 422 for paddle events other than `transaction.completed`
        HTTPException: 404 if an item references an unknown product license
        HTTPException: 502 if the customer cannot be retrieved from Paddle API
    """
    paddle: Paddle = request.app.state.paddle
    licensing: Licensing = request.app.state.licensing

    # Certify request comes from Paddle webhook
    if not await paddle.validate_webhook_signature(request):
        raise HTTPException(
            status_code=401,
            detail="Cannot validate webhook signature"
        )
    
    # Retrieve user
    try:
        customer = await paddle.get_customer(body.data.customer_id)
    except ApiError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Cannot retrieve Paddle customer '{body.data.customer_id}': {e.error_code}"
        )
    except RequestException:
        raise HTTPException(
            status_code=502,
            detail="Paddle API unreachable"
        )

    # Create license
    try:
        order_request = body.build_order_request(customer)
        license_keys = licensing.create_licenses(order_request)
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
