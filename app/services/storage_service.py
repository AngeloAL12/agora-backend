import logging
import uuid
from pathlib import Path

import aioboto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile

from app.core.config import settings

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}
ALLOWED_IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg"}

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURES = (b"\xff\xd8\xff",)


def _get_file_extension(filename: str) -> str:
    return Path(filename).suffix.lower().removeprefix(".")


async def _validate_image_upload(file: UploadFile) -> str:
    filename = file.filename or ""
    extension = _get_file_extension(filename)

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail="Extensión de archivo inválida. Solo se permiten: png, jpg, jpeg.",
        )

    if file.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail="Content-Type inválido. Solo se permiten imágenes PNG o JPEG.",
        )

    header = await file.read(16)
    await file.seek(0)

    is_png = extension == "png" and header.startswith(PNG_SIGNATURE)
    is_jpeg = extension in {"jpg", "jpeg"} and header.startswith(JPEG_SIGNATURES)

    if not is_png and not is_jpeg:
        raise HTTPException(
            status_code=422,
            detail="El contenido del archivo no corresponde a una imagen válida.",
        )

    return extension


class StorageService:
    def __init__(self):
        self._session = aioboto3.Session(
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )
        self._endpoint_url = settings.R2_ENDPOINT

    async def upload_file(self, file: UploadFile, bucket_name: str, prefix: str) -> str:
        extension = await _validate_image_upload(file)
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
                detail="No se pudo eliminar el archivo.",
            ) from e

    async def get_presigned_url(
        self, bucket_name: str, object_key: str, expiration: int = 3600
    ) -> str:
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


storage_service = StorageService()
