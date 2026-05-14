from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, Request, status

from modules.upload_files.schema import *
import logging

logger = logging.getLogger(__name__)

class DirectGCSUploads:
    def __init__(self):
        pass
    
    
    async def bulk_generate_upload_urls(
        self, request: Request, files: list[GenerateGCSUploadURL]
    ) -> list[GCSUploadURLResponse]:
        logger.info("[LOG] Generating URLs for direct GCS upload...")

        # validate object len
        if len(files) < 1:
            logger.error(f"[ERROR] Triggered this service but no actual files metadata found.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No files found...",
            )
        
        now = datetime.now().strftime("%Y-%m-%d")
        ip = str(request.client.host if request.client else "unknown")
        for file in files:
            storage_path = self.construct_gcs_storage_path(
                file_name=file.file_name, date=now, id=str(uuid4(), ip=ip)
            )
            
            
            

    def construct_gcs_storage_path(self, file_name: str, date: str, id: str, ip: str = "unknown") -> str:
        return f"api/public/upload/{ip}/{date}/{id}/{file_name}"
    