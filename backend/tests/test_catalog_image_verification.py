import io
import hashlib

import pytest
from PIL import Image

from catalog.media import verify_product_image
from catalog.portability.schema import ErrorCode
from media_storage.errors import MediaError


def image_bytes(format_name):
    output = io.BytesIO()
    image = Image.new("RGB", (3, 2), (10, 20, 30))
    image.save(output, format=format_name)
    return output.getvalue()


@pytest.mark.parametrize("format_name,content_type,extension", [("JPEG", "image/jpeg", "jpg"), ("PNG", "image/png", "png"), ("WEBP", "image/webp", "webp")])
def test_supported_images_are_verified_without_changing_bytes(format_name, content_type, extension):
    content = image_bytes(format_name)
    prepared = verify_product_image(content, asserted_content_type=content_type)
    assert prepared.content == content
    assert prepared.content_type == content_type
    assert prepared.extension == extension
    assert prepared.asset_path == f"media/{hashlib.sha256(content).hexdigest()}.{extension}"
    assert (prepared.width, prepared.height) == (3, 2)


@pytest.mark.parametrize("content", [b"", b"<svg></svg>", b"not an image"])
def test_invalid_images_are_rejected(content):
    with pytest.raises(MediaError) as error:
        verify_product_image(content)
    assert error.value.code in {ErrorCode.INVALID_IMAGE, ErrorCode.LIMIT_EXCEEDED}


def test_descriptor_digest_size_type_and_asset_path_are_verified():
    content = image_bytes("PNG")
    digest = hashlib.sha256(content).hexdigest()
    expected = {"sha256": digest, "size_bytes": len(content), "media_type": "image/png", "path": f"media/{digest}.png"}
    assert verify_product_image(content, expected=expected).sha256 == digest
    expected["sha256"] = "0" * 64
    with pytest.raises(MediaError) as error:
        verify_product_image(content, expected=expected)
    assert error.value.code == ErrorCode.INVALID_PACKAGE


def test_mime_assertion_cannot_override_decoded_format():
    with pytest.raises(MediaError):
        verify_product_image(image_bytes("PNG"), asserted_content_type="image/jpeg")
