import io
from pathlib import Path
from PIL import Image
import pytest

from app.models.entities import Product, RoomDesignGeneration, RoomProject
from app.services.storage_service import RoomImageStorageService
from test_recommendations import auth_headers, create_project, setup_recommendation_case

PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"


def make_valid_jpeg() -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (64, 64), (200, 200, 200))
    img.save(buf, format="JPEG")
    return buf.getvalue()


def make_valid_png() -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGBA", (64, 64), (100, 150, 200, 255))
    img.save(buf, format="PNG")
    return buf.getvalue()


def add_room_image(db_session, project: dict) -> None:
    storage = RoomImageStorageService()
    relative_path = Path(str(project["user_id"])) / str(project["id"]) / "source.png"
    absolute_path = storage.storage_root / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(PNG_BYTES)

    room_project = db_session.get(RoomProject, project["id"])
    room_project.room_image_url = f"/storage/rooms/{project['user_id']}/{project['id']}/source.png"
    room_project.room_image_path = str(relative_path).replace("\\", "/")
    room_project.image_original_filename = "source.png"
    room_project.image_content_type = "image/png"
    room_project.image_size_bytes = len(PNG_BYTES)
    room_project.image_checksum = "phase6checksum"
    room_project.status = "COMPLETED"
    db_session.commit()


def test_import_gemini_manual_design_success_png(client, db_session):
    headers, project, _catalog, best, lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)

    png_data = make_valid_png()
    files = {"file": ("gemini_sofa_design.png", png_data, "image/png")}
    data = {
        "product_ids": f"{best.id},{lamp.id}",
        "notes": "Ảnh tải từ Gemini Advanced web app",
    }

    response = client.post(
        f"/api/room-projects/{project['id']}/design-generations/import-gemini",
        files=files,
        data=data,
        headers=headers,
    )

    assert response.status_code == 201, response.text
    payload = response.json()

    assert payload["status"] == "COMPLETED"
    assert payload["provider"] == "gemini_manual_import"
    assert payload["model"] == "gemini-web-app"
    assert payload["generation_mode"] == "AI_PHOTOREALISTIC_PREVIEW"
    assert payload["is_ai_preview"] is True
    assert payload["verification_status"] == "NEEDS_REVIEW"
    assert payload["verification_details"]["is_catalog_exact"] is False
    assert payload["verification_details"]["source_type"] == "GEMINI_WEB_APP_MANUAL"
    assert "Ảnh phối cảnh tạo bằng ứng dụng Gemini — nhập thủ công" in payload["verification_details"]["source_label"]
    assert payload["verification_details"]["api_used"] is False

    # Check products linked
    returned_product_ids = {p["id"] for p in payload["products"]}
    assert returned_product_ids == {best.id, lamp.id}

    # Verify original room image unchanged
    room_db = db_session.get(RoomProject, project["id"])
    assert room_db.room_image_path == f"{project['user_id']}/{project['id']}/source.png"


def test_import_gemini_manual_design_success_jpeg(client, db_session):
    headers, project, _catalog, best, lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)

    jpeg_data = make_valid_jpeg()
    files = {"file": ("gemini_sofa_design.jpg", jpeg_data, "image/jpeg")}
    data = {"product_ids": f"[{best.id}]"}

    response = client.post(
        f"/api/room-projects/{project['id']}/design-generations/import-gemini",
        files=files,
        data=data,
        headers=headers,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["provider"] == "gemini_manual_import"
    assert payload["verification_status"] == "NEEDS_REVIEW"
    assert len(payload["products"]) == 1
    assert payload["products"][0]["id"] == best.id


def test_import_gemini_manual_design_persistence_after_reload(client, db_session):
    headers, project, _catalog, best, lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)

    png_data = make_valid_png()
    files = {"file": ("gemini_render.png", png_data, "image/png")}
    data = {"product_ids": f"{best.id}"}

    create_resp = client.post(
        f"/api/room-projects/{project['id']}/design-generations/import-gemini",
        files=files,
        data=data,
        headers=headers,
    )
    assert create_resp.status_code == 201
    gen_id = create_resp.json()["id"]

    # Reload 1: GET specific generation
    get_resp = client.get(
        f"/api/room-projects/{project['id']}/design-generations/{gen_id}",
        headers=headers,
    )
    assert get_resp.status_code == 200
    get_payload = get_resp.json()
    assert get_payload["generation_mode"] == "AI_PHOTOREALISTIC_PREVIEW"
    assert get_payload["is_ai_preview"] is True
    assert get_payload["verification_status"] == "NEEDS_REVIEW"
    assert get_payload["provider"] == "gemini_manual_import"

    # Reload 2: List all generations
    list_resp = client.get(
        f"/api/room-projects/{project['id']}/design-generations",
        headers=headers,
    )
    assert list_resp.status_code == 200
    list_items = list_resp.json()["items"]
    imported_item = next((item for item in list_items if item["id"] == gen_id), None)
    assert imported_item is not None
    assert imported_item["verification_status"] == "NEEDS_REVIEW"
    assert imported_item["is_ai_preview"] is True


def test_import_gemini_manual_design_rejects_unowned_project(client, db_session):
    headers1, project1, _catalog, best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project1)

    # Second user
    headers2 = auth_headers(client, email="other_user@example.com")

    png_data = make_valid_png()
    files = {"file": ("gemini.png", png_data, "image/png")}
    data = {"product_ids": f"{best.id}"}

    response = client.post(
        f"/api/room-projects/{project1['id']}/design-generations/import-gemini",
        files=files,
        data=data,
        headers=headers2,
    )
    assert response.status_code == 404


def test_import_gemini_manual_design_rejects_invalid_file_signature(client, db_session):
    headers, project, _catalog, best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)

    corrupt_data = b"This is a text file masquerading as PNG"
    files = {"file": ("fake.png", corrupt_data, "image/png")}
    data = {"product_ids": f"{best.id}"}

    response = client.post(
        f"/api/room-projects/{project['id']}/design-generations/import-gemini",
        files=files,
        data=data,
        headers=headers,
    )
    assert response.status_code == 400
    assert "chữ ký" in response.text or "signature" in response.text.lower() or "invalid" in response.text.lower()


def test_import_gemini_manual_design_rejects_empty_file(client, db_session):
    headers, project, _catalog, best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)

    files = {"file": ("empty.png", b"", "image/png")}
    data = {"product_ids": f"{best.id}"}

    response = client.post(
        f"/api/room-projects/{project['id']}/design-generations/import-gemini",
        files=files,
        data=data,
        headers=headers,
    )
    assert response.status_code == 400


def test_import_gemini_manual_design_rejects_missing_product_ids(client, db_session):
    headers, project, _catalog, _best, _lamp, _mismatch, _inactive = setup_recommendation_case(client, db_session)
    add_room_image(db_session, project)

    png_data = make_valid_png()
    files = {"file": ("gemini.png", png_data, "image/png")}
    data = {"product_ids": ""}

    response = client.post(
        f"/api/room-projects/{project['id']}/design-generations/import-gemini",
        files=files,
        data=data,
        headers=headers,
    )
    assert response.status_code == 400
