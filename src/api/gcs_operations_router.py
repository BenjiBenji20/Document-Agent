from fastapi import APIRouter, Depends

from src.dependencies.rate_limit import rate_limit_by_ip
from src.dependencies.secrets import document_agent_secret
from src.modules.gcs_operations.direct_gcs_operations_schema import GCSUploadURLResponse, GCSUploadFileMetadata
from src.modules.gcs_operations.direct_gcs_operations_service import DirectGCSOperationsService


router = APIRouter(
    prefix="/api/public/gcs",  
    tags=[
        "Bulk gcs signed upload URL generation",
    ]
)

@router.post(
    "/generate-upload-urls",
    response_model=list[GCSUploadURLResponse],
    dependencies=[
        Depends(document_agent_secret),
        Depends(rate_limit_by_ip())
    ],
    summary="Get direct GCS upload URLs"
)
async def generate_upload_urls(
    files: list[GCSUploadFileMetadata]
):
    gcs_ops_service = DirectGCSOperationsService()
    return await gcs_ops_service.bulk_generate_gcs_upload_urls(files)
