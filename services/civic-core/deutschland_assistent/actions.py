from __future__ import annotations

import io
import threading
import time
import uuid
from dataclasses import dataclass, replace

from pypdf import PdfReader, PdfWriter

from .schemas import ActionPreview, FormFieldInfo, FormInspection


@dataclass
class StoredAction:
    created: float
    preview: ActionPreview
    artifact: bytes | None = None
    artifact_name: str | None = None


@dataclass
class StoredForm:
    created: float
    filename: str
    data: bytes
    fields: list[FormFieldInfo]


class ActionStore:
    def __init__(self, ttl_seconds: int = 3600, max_items: int = 300):
        self.ttl = ttl_seconds
        self.max_items = max_items
        self._actions: dict[str, StoredAction] = {}
        self._forms: dict[str, StoredForm] = {}
        self._lock = threading.Lock()

    def _purge(self):
        now = time.monotonic()
        for mapping in (self._actions, self._forms):
            for key in [k for k, v in mapping.items() if now - v.created > self.ttl]:
                mapping.pop(key, None)
            while len(mapping) > self.max_items:
                oldest = min(mapping, key=lambda k: mapping[k].created)
                mapping.pop(oldest, None)

    def put_action(self, preview: ActionPreview, artifact: bytes | None = None, artifact_name: str | None = None):
        with self._lock:
            self._purge()
            self._actions[preview.action_id] = StoredAction(time.monotonic(), preview, artifact, artifact_name)

    def get_action(self, action_id: str) -> StoredAction | None:
        with self._lock:
            self._purge()
            return self._actions.get(action_id)

    def update_action(self, action_id: str, preview: ActionPreview, artifact: bytes | None = None, artifact_name: str | None = None):
        with self._lock:
            self._purge()
            current = self._actions.get(action_id)
            if not current:
                return False
            self._actions[action_id] = StoredAction(
                current.created,
                preview,
                artifact if artifact is not None else current.artifact,
                artifact_name if artifact_name is not None else current.artifact_name,
            )
            return True

    def put_form(self, form: StoredForm) -> str:
        form_id = "form_" + uuid.uuid4().hex[:16]
        with self._lock:
            self._purge()
            self._forms[form_id] = form
        return form_id

    def get_form(self, form_id: str) -> StoredForm | None:
        with self._lock:
            self._purge()
            return self._forms.get(form_id)


def inspect_pdf_form(data: bytes, filename: str, ttl_seconds: int, store: ActionStore) -> FormInspection:
    reader = PdfReader(io.BytesIO(data))
    raw_fields = reader.get_fields() or {}
    fields: list[FormFieldInfo] = []
    for name, meta in raw_fields.items():
        field_type = str(meta.get("/FT") or "")
        value = meta.get("/V")
        options = meta.get("/Opt") or []
        if not isinstance(options, list):
            options = [str(options)]
        fields.append(
            FormFieldInfo(
                name=str(name),
                label=str(meta.get("/TU") or meta.get("/T") or name),
                field_type=field_type,
                current_value=str(value) if value is not None else None,
                options=[str(x) for x in options[:50]],
            )
        )
    stored = StoredForm(
        created=time.monotonic(),
        filename=filename,
        data=data,
        fields=fields,
    )
    form_id = store.put_form(stored)
    return FormInspection(
        form_id=form_id,
        filename=filename,
        fields=fields,
        expires_in_seconds=ttl_seconds,
    )


def fill_pdf_form(data: bytes, values: dict[str, str]) -> bytes:
    reader = PdfReader(io.BytesIO(data))
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    for page in writer.pages:
        writer.update_page_form_field_values(page, values, auto_regenerate=True)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def new_action(
    action_type: str,
    summary: str,
    payload: dict,
    execution_target: str,
    ttl_seconds: int,
) -> ActionPreview:
    return ActionPreview(
        action_id="act_" + uuid.uuid4().hex[:16],
        action_type=action_type,
        status="prepared",
        version=1,
        summary=summary,
        payload=payload,
        requires_confirmation=True,
        execution_target=execution_target,
        expires_in_seconds=ttl_seconds,
    )
