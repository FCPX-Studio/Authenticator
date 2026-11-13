from fastapi import APIRouter, Request, HTTPException

from app.schemas.requests import OrderLicenseRequest, ActivateLicenseRequest
from app.schemas.license import LicenseToken
from app.schemas.exceptions import InvalideLicenseKeyError, ExpiredLicenseError, ActivationLimitReachedError
from app.services.licensing import Licensing


router = APIRouter(
    prefix='/license',
    tags=["license"]
)


@router.post('/create')
async def create(body: OrderLicenseRequest, request: Request) -> list[str]:
    """
    Create license keys for an order

    Args:
        body (CreateLicenseRequest): Information about the products to license
        request (Request): Default request argument
    """
    licensing: Licensing = request.app.state.licensing

    #TODO: Protect access 
    # (/create can only be called from fcpxstudio webside when a product is bought)

    license_key = licensing.create_licenses(body)
    
    return license_key

@router.post('/activate', response_model=LicenseToken)
async def activate(body: ActivateLicenseRequest, request: Request) -> LicenseToken | HTTPException:
    """
    Validate and activate a license for a specific machine

    Args:
        body (ActivateLicenseRequest): License and machine informations
        request (Request): Default request argument

    Returns:
        LicenseToken: Signed token FxPlug can validate
    """
    licensing: Licensing = request.app.state.licensing

    try:
        token = licensing.activate_license(body)
    except InvalideLicenseKeyError as e:
        return HTTPException(
            status_code=404, 
            detail=f"Invalid license key '{e.license_key}'"
        )
    except ExpiredLicenseError as e:
        return HTTPException(
            status_code=403,
            detail=f"License expired on {e.expiration_date}"
        )
    except ActivationLimitReachedError as e:
        return HTTPException(
            status_code=409,
            detail=f"Activation limit reached: {e.activation_limit} / {e.activation_limit} computer registered"
        )

    return token