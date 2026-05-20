import asyncio
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, Request, status

from src.core.settings import settings
from src.infrastructure.gcs_service import gcs_service
from src.modules.gcs_operations.schema import *
import logging

logger = logging.getLogger(__name__)

class DirectGCSOperationsService:
    def __init__(self, request: Request):
        self.request = request
    
    async def bulk_generate_gcs_upload_urls(
        self, files: list[UploadFileMetadata]
    ) -> list[GCSUploadURLResponse]:
        logger.info("[LOG] Generating URLs for direct GCS upload...")

        # validate object len
        if len(files) < 1:
            logger.error(f"[ERROR] Triggered this service but no actual files metadata found.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No files found...",
            )
        
        try:
            results: list[GCSUploadURLResponse] = []
            
            ip = str(self.request.client.host if self.request.client else "unknown")
            now = datetime.now().strftime("%Y-%m-%d")
            for file in files:
                id = str(uuid4())
                storage_path = gcs_service.get_gcs_storage_path(
                    file_name=file.file_name, date=now, id=id, ip=ip
                )
            
                logger.info(f"[LOG] Generating GCS signed URI for file {file.file_name}")
                upload_url = await asyncio.to_thread(
                    gcs_service.generate_signed_upload_url,
                    storage_path,
                    file.file_type
                )

                results.append(
                    GCSUploadURLResponse(
                        id=id,
                        upload_url=upload_url,
                        storage_path=storage_path,
                        expires_in_seconds=settings.GCS_SIGNED_URL_EXPIRATION
                    )
                )
            
            logger.info(f"[LOG] Returning list of GCS signed URI.")
            return results
        
        except Exception:
            logger.critical("[CRITICAL] SERVER ERROR...")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server error while uploading file."
            )
    
    
    async def generate_gcs_download_url(
        self, 
        file_id: str, 
        file_name: str, 
        date: str = datetime.now().strftime("%Y-%m-%d")
    ) -> GCSDownloadURLResponse:
        """Method use by model to download the file directly from GCS."""
        logger.info("[LOG] Generating URLs for direct GCS download to file...")
        
        try:
            ip = str(self.request.client.host if self.request.client else "unknown")
            storage_path = gcs_service.get_gcs_storage_path(
                file_name=file_name, date=date, id=file_id, ip=ip
            )
            
            download_url = await asyncio.to_thread(
                gcs_service.generate_signed_download_url,
                storage_path
            )
            
            if not download_url:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No files to download found using this GCS storage path: {storage_path}"
                )
                
            return GCSDownloadURLResponse(
                id=file_id,
                storage_path=storage_path,
                expires_in_seconds=settings.GCS_SIGNED_URL_EXPIRATION
            )
            
        except Exception:
            logger.critical("[CRITICAL] SERVER ERROR...")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server error while uploading file."
            )
        