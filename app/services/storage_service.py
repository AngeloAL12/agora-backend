import logging
import uuid

import aioboto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self):
        self._session = aioboto3.Session(
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )
        self._endpoint_url = settings.R2_ENDPOINT

    async def upload_file(self, file: UploadFile, bucket_name: str, prefix: str) -> str:
        """
        Sube un archivo a R2 y retorna el 'Object Key' (la ruta guardada).
        Ejemplo de prefix: "complaints/1042/images" o "clubs/12/posts/899"
        """
        filename = file.filename or ""
        extension = filename.split(".")[-1] if "." in filename else "bin"
        unique_filename = f"{uuid.uuid4()}.{extension}"
        object_key = f"{prefix}/{unique_filename}"

        try:
            async with self._session.client(
                "s3", endpoint_url=self._endpoint_url
            ) as s3:  # type: ignore
                await s3.upload_fileobj(
                    file.file,
                    bucket_name,
                    object_key,
                    ExtraArgs={"ContentType": file.content_type},
                )
            return object_key

        except ClientError as e:
            logger.error(f"Error subiendo archivo a R2: {e}")
            raise HTTPException(
                status_code=500,
                detail="Ocurrió un error al subir el archivo a la nube.",
            ) from e

    async def delete_file(self, bucket_name: str, object_key: str) -> None:
        """
        Elimina un objeto de R2 dado su bucket y object key.
        """
        try:
            async with self._session.client(
                "s3", endpoint_url=self._endpoint_url
            ) as s3:  # type: ignore
                await s3.delete_object(Bucket=bucket_name, Key=object_key)
        except ClientError as e:
            logger.error(f"Error eliminando archivo en R2: {e}")
            raise HTTPException(
                status_code=500,
                detail="Ocurrió un error al eliminar el archivo anterior en la nube.",
            ) from e

    async def get_presigned_url(
        self, bucket_name: str, object_key: str, expiration: int = 3600
    ) -> str:
        """
        Genera una URL firmada temporal para acceder a archivos del bucket privado.
        expiration: tiempo de vida en segundos (3600 = 1 hora).
        """
        try:
            async with self._session.client(
                "s3", endpoint_url=self._endpoint_url
            ) as s3:  # type: ignore
                url = await s3.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={"Bucket": bucket_name, "Key": object_key},
                    ExpiresIn=expiration,
                )
            return url

        except ClientError as e:
            logger.error(f"Error generando URL firmada: {e}")
            raise HTTPException(
                status_code=500,
                detail="No se pudo generar el enlace seguro de la imagen.",
            ) from e


# Instancia global para importarla en los endpoints
storage_service = StorageService()
