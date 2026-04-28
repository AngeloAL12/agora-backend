from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile

from app.services.storage_service import StorageService


def make_upload_file(
    filename: str = "test.jpg", content_type: str = "image/jpeg"
) -> UploadFile:
    return UploadFile(
        filename=filename,
        file=BytesIO(b"fake-image-content"),
        headers={"content-type": content_type},
    )


def make_client_error() -> ClientError:
    return ClientError(
        error_response={
            "Error": {"Code": "NoSuchBucket", "Message": "The bucket does not exist"}
        },
        operation_name="PutObject",
    )


@pytest.fixture
def service():
    return StorageService()


@pytest.fixture
def mock_s3_client():
    """Async context manager mock for aioboto3 session.client()."""
    client = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, client


# ---------------------------------------------------------------------------
# upload_file
# ---------------------------------------------------------------------------


async def test_upload_file_returns_object_key(service, mock_s3_client):
    cm, client = mock_s3_client
    client.upload_fileobj = AsyncMock(return_value=None)

    with patch.object(service._session, "client", return_value=cm):
        file = make_upload_file("photo.png", "image/png")
        result = await service.upload_file(file, "my-bucket", "complaints/1/images")

    assert result.startswith("complaints/1/images/")
    assert result.endswith(".png")
    client.upload_fileobj.assert_awaited_once()


async def test_upload_file_uses_correct_bucket_and_content_type(
    service, mock_s3_client
):
    cm, client = mock_s3_client
    client.upload_fileobj = AsyncMock(return_value=None)

    with patch.object(service._session, "client", return_value=cm):
        file = make_upload_file("doc.pdf", "application/pdf")
        await service.upload_file(file, "target-bucket", "docs")

    _, call_kwargs = client.upload_fileobj.call_args
    assert client.upload_fileobj.call_args[0][1] == "target-bucket"
    assert (
        client.upload_fileobj.call_args[1]["ExtraArgs"]["ContentType"]
        == "application/pdf"
    )


async def test_upload_file_no_extension_defaults_to_bin(service, mock_s3_client):
    cm, client = mock_s3_client
    client.upload_fileobj = AsyncMock(return_value=None)

    with patch.object(service._session, "client", return_value=cm):
        file = make_upload_file("noextension", "application/octet-stream")
        result = await service.upload_file(file, "bucket", "prefix")

    assert result.endswith(".bin")


async def test_upload_file_raises_http_exception_on_client_error(
    service, mock_s3_client
):
    cm, client = mock_s3_client
    client.upload_fileobj = AsyncMock(side_effect=make_client_error())

    with patch.object(service._session, "client", return_value=cm):
        file = make_upload_file()
        with pytest.raises(HTTPException) as exc_info:
            await service.upload_file(file, "bucket", "prefix")

    assert exc_info.value.status_code == 500
    assert "subir" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# delete_file
# ---------------------------------------------------------------------------


async def test_delete_file_calls_delete_object(service, mock_s3_client):
    cm, client = mock_s3_client
    client.delete_object = AsyncMock(return_value=None)

    with patch.object(service._session, "client", return_value=cm):
        await service.delete_file("private-bucket", "complaints/1/evidence/file.png")

    client.delete_object.assert_awaited_once_with(
        Bucket="private-bucket", Key="complaints/1/evidence/file.png"
    )


async def test_delete_file_raises_http_exception_on_client_error(
    service, mock_s3_client
):
    cm, client = mock_s3_client
    client.delete_object = AsyncMock(side_effect=make_client_error())

    with patch.object(service._session, "client", return_value=cm):
        with pytest.raises(HTTPException) as exc_info:
            await service.delete_file("bucket", "key.jpg")

    assert exc_info.value.status_code == 500
    assert "eliminar" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# get_presigned_url
# ---------------------------------------------------------------------------


async def test_get_presigned_url_returns_url(service, mock_s3_client):
    cm, client = mock_s3_client
    client.generate_presigned_url = AsyncMock(
        return_value="https://r2.example.com/signed"
    )

    with patch.object(service._session, "client", return_value=cm):
        result = await service.get_presigned_url(
            "private-bucket", "complaints/1/image.jpg"
        )

    assert result == "https://r2.example.com/signed"


async def test_get_presigned_url_passes_correct_params(service, mock_s3_client):
    cm, client = mock_s3_client
    client.generate_presigned_url = AsyncMock(
        return_value="https://r2.example.com/signed"
    )

    with patch.object(service._session, "client", return_value=cm):
        await service.get_presigned_url(
            "my-bucket", "path/to/file.jpg", expiration=7200
        )

    client.generate_presigned_url.assert_awaited_once_with(
        ClientMethod="get_object",
        Params={"Bucket": "my-bucket", "Key": "path/to/file.jpg"},
        ExpiresIn=7200,
    )


async def test_get_presigned_url_raises_http_exception_on_client_error(
    service, mock_s3_client
):
    cm, client = mock_s3_client
    client.generate_presigned_url = AsyncMock(side_effect=make_client_error())

    with patch.object(service._session, "client", return_value=cm):
        with pytest.raises(HTTPException) as exc_info:
            await service.get_presigned_url("bucket", "key.jpg")

    assert exc_info.value.status_code == 500
    assert "enlace" in exc_info.value.detail.lower()
