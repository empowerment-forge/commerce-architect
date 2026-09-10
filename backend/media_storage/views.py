from django.http import Http404, HttpResponse
from django.views.decorators.http import require_http_methods

from .configuration import get_media_storage
from .errors import MediaError
from .keys import validate_storage_key


@require_http_methods(["GET", "HEAD"])
def local_media(request, digest):
    if request.method not in {"GET", "HEAD"}:
        raise Http404
    try:
        stored = get_media_storage().read_verified(f"sha256/{digest}", 10 * 1024 * 1024)
    except MediaError as exc:
        if exc.code.value == "OPERATION_NOT_ALLOWED":
            raise Http404
        raise Http404
    response = HttpResponse(stored.content if request.method == "GET" else b"", content_type=stored.content_type)
    response["Content-Length"] = str(stored.size_bytes)
    response["Content-Disposition"] = "inline"
    response["Cache-Control"] = "public, max-age=31536000, immutable"
    response["X-Content-Type-Options"] = "nosniff"
    return response
