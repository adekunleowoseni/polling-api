from __future__ import annotations

from typing import Any

from google.api_core.client_options import ClientOptions
from google.cloud import documentai

from .settings import settings


def _match_field(parsed: dict[str, Any], aliases: list[str]) -> str | None:
    for alias in aliases:
        value = parsed.get(alias)
        if value:
            return str(value).strip()
    return None


def parse_document_fields(raw_payload: dict[str, Any]) -> dict[str, Any]:
    entities = raw_payload.get("entities", [])
    flat: dict[str, str] = {}

    for entity in entities:
        key = str(entity.get("type", "")).lower()
        value = str(entity.get("mentionText", "")).strip()
        if key and value:
            flat[key] = value

    return {
        "name": _match_field(flat, ["name", "full_name", "person_name"]),
        "phone": _match_field(flat, ["phone", "phone_number", "mobile"]),
        "email": _match_field(flat, ["email", "email_address"]),
        "ward": _match_field(flat, ["ward", "district", "zone"]),
        "lga": _match_field(flat, ["lga", "local_government", "local_government_area"]),
        "polling_unit": _match_field(
            flat,
            ["polling_unit", "polling unit", "pu", "pu_code", "polling_unit_code"],
        ),
        "address": _match_field(flat, ["address", "home_address"]),
        "form_date": _match_field(flat, ["date", "registration_date"]),
    }


def extract_with_document_ai(content: bytes, mime_type: str) -> tuple[dict[str, Any], dict[str, Any]]:
    client_options = ClientOptions(
        api_endpoint=f"{settings.google_cloud_location}-documentai.googleapis.com"
    )
    client = documentai.DocumentProcessorServiceClient(client_options=client_options)

    processor_name = client.processor_path(
        settings.google_cloud_project_id,
        settings.google_cloud_location,
        settings.google_documentai_processor_id,
    )

    request = documentai.ProcessRequest(
        name=processor_name,
        raw_document=documentai.RawDocument(content=content, mime_type=mime_type),
    )
    result = client.process_document(request=request)
    document_dict = documentai.Document.to_dict(result.document)

    parsed_fields = parse_document_fields(document_dict)
    return parsed_fields, document_dict
