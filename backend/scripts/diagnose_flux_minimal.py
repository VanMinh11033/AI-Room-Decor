"""One-shot, read-only-input diagnostic for Cloudflare FLUX.2 [dev].

Running this script sends exactly one billable inference request. It does not
write to the database, save the response, or retry. Do not run without approval.
"""

import json
from time import perf_counter

import httpx

from app.ai.image.cloudflare_provider import CloudflareImageProvider
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.entities import RoomProject
from app.services.storage_service import RoomImageStorageService


PROJECT_ID = 17
MODEL = "@cf/black-forest-labs/flux-2-dev"
PROMPT = (
    "Add a modern beige sofa to this room. Preserve the original walls, floor, "
    "windows, camera angle and room layout."
)
STEPS = 25


def main() -> None:
    if not settings.cloudflare_account_id or not settings.cloudflare_api_token:
        raise SystemExit("Cloudflare account ID or API token is not configured.")
    if settings.image_model != MODEL:
        raise SystemExit(f"Configured model must be {MODEL}; refusing to send request.")

    # Read the existing image reference from Project 17; this session performs
    # SELECT only and is always closed before the outbound inference request.
    db = SessionLocal()
    try:
        project = db.get(RoomProject, PROJECT_ID)
        if project is None or not project.room_image_path:
            raise SystemExit(f"Project {PROJECT_ID} has no room image.")
        source_path = RoomImageStorageService().resolve(project.room_image_path)
    finally:
        db.close()

    if not source_path.is_file():
        raise SystemExit(f"Project {PROJECT_ID} room image file is missing.")

    # Reuse the provider's local resize/JPEG preparation only. This does not
    # call the provider or make any network request.
    preparer = CloudflareImageProvider(
        account_id=settings.cloudflare_account_id,
        api_token=settings.cloudflare_api_token,
        model_name=MODEL,
        max_retries=0,
    )
    image_bytes, mime_type, filename = preparer._prepare_input_image(source_path)
    url = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{settings.cloudflare_account_id}/ai/run/{MODEL}"
    )
    files = {"input_image_0": (filename, image_bytes, mime_type)}
    form = {"prompt": PROMPT, "steps": str(STEPS)}

    print(f"project_id={PROJECT_ID}")
    print(f"model={MODEL}")
    print(f"image_field=input_image_0 mime={mime_type} bytes={len(image_bytes)}")
    print(f"prompt={PROMPT}")
    print(f"steps={STEPS}")
    print("retries=0; outbound_request_limit=1")

    started = perf_counter()
    try:
        # httpx does not retry requests by default; this is the script's sole
        # client.post call, with redirects disabled as well.
        with httpx.Client(
            timeout=httpx.Timeout(
                connect=10,
                read=settings.cloudflare_image_timeout_seconds,
                write=30,
                pool=10,
            ),
            follow_redirects=False,
        ) as client:
            response = client.post(
                url,
                headers={"Authorization": f"Bearer {settings.cloudflare_api_token}"},
                data=form,
                files=files,
            )
    except httpx.HTTPError as exc:
        print("requests_attempted=1")
        print(f"elapsed_ms={round((perf_counter() - started) * 1000)}")
        print(f"transport_error={type(exc).__name__}: {str(exc)[:500]}")
        raise SystemExit(2) from None

    elapsed_ms = round((perf_counter() - started) * 1000)
    print("requests_attempted=1")
    print(f"http_status={response.status_code}")
    print(
        "cloudflare_request_id="
        f"{response.headers.get('cf-ray') or response.headers.get('cf-request-id') or 'not returned'}"
    )
    print(f"response_content_type={response.headers.get('content-type', 'unknown')}")
    print(f"elapsed_ms={elapsed_ms}")

    try:
        body = response.json()
    except (ValueError, json.JSONDecodeError):
        print(f"error_code=unavailable; response_body={response.text[:500]}")
        return

    errors = body.get("errors", []) if isinstance(body, dict) else []
    if errors:
        first_error = errors[0] if isinstance(errors[0], dict) else {}
        print(f"error_code={first_error.get('code', 'unknown')}")
        print(f"error_message={str(first_error.get('message', ''))[:500]}")
    else:
        print(f"error_code={'none' if response.is_success else 'unavailable'}")
        print(f"cloudflare_success={body.get('success') if isinstance(body, dict) else 'unknown'}")


if __name__ == "__main__":
    main()
