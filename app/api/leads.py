"""CRUD endpoints for sales leads."""

import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.lead import LeadCreate, LeadResponse, LeadUpdate
from database.models import Lead

router = APIRouter(prefix="/leads", tags=["leads"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post("/", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
def create_lead(payload: LeadCreate, db: DatabaseSession) -> Lead:
    """Create and return a new lead."""
    lead = Lead(**payload.model_dump())
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


@router.get("/", response_model=list[LeadResponse])
def list_leads(
    db: DatabaseSession,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    lead_status: str | None = None,
    industry: str | None = None,
) -> list[Lead]:
    """Return a page of leads, optionally filtered by status and industry."""
    statement = select(Lead)
    if lead_status is not None:
        statement = statement.where(Lead.lead_status == lead_status)
    if industry is not None:
        statement = statement.where(Lead.industry == industry)
    statement = statement.order_by(Lead.lead_id).offset(skip).limit(limit)
    return list(db.scalars(statement).all())


@router.post("/upload-csv")
async def upload_leads_csv(
    file: Annotated[UploadFile, File(description="CSV file containing lead records")],
    db: DatabaseSession,
) -> dict[str, object]:
    """Validate a CSV file, skip duplicate leads, and bulk insert valid rows.

    Required CSV headers are ``company_name``, ``industry``, and
    ``contact_name``. Invalid rows are reported individually while valid rows
    continue through the import.
    """
    summary: dict[str, object] = {
        "total_rows": 0,
        "inserted": 0,
        "duplicates_skipped": 0,
        "errors": [],
    }
    errors: list[dict[str, object]] = summary["errors"]  # type: ignore[assignment]

    raw_content = await file.read()
    if not raw_content:
        return summary

    try:
        try:
            content = raw_content.decode("utf-8-sig")
        except UnicodeDecodeError:
            # Windows-created CSVs are commonly encoded as Windows-1252.
            content = raw_content.decode("cp1252")
    except UnicodeDecodeError:
        errors.append({"row": 0, "error": "File must use UTF-8 or Windows-1252 encoding."})
        return summary

    try:
        reader = csv.DictReader(io.StringIO(content, newline=""))
        if reader.fieldnames is None:
            return summary
        reader.fieldnames = [name.strip() if name else "" for name in reader.fieldnames]
        required_columns = {"company_name", "industry", "contact_name"}
        missing_columns = sorted(required_columns - set(reader.fieldnames))
        if missing_columns:
            errors.append(
                {
                    "row": 1,
                    "error": f"Missing required columns: {', '.join(missing_columns)}.",
                }
            )
            return summary

        candidates: list[tuple[int, dict[str, object]]] = []
        for row_number, row in enumerate(reader, start=2):
            if row is None or all(value is None or not value.strip() for value in row.values()):
                continue
            summary["total_rows"] = int(summary["total_rows"]) + 1
            if None in row:
                errors.append({"row": row_number, "error": "Row contains more values than the header."})
                continue
            normalized_row = {
                key: value.strip() if isinstance(value, str) else value
                for key, value in row.items()
                if key is not None
            }
            try:
                lead_data = LeadCreate.model_validate(normalized_row).model_dump()
            except ValidationError as exc:
                errors.append(
                    {"row": row_number, "error": "; ".join(error["msg"] for error in exc.errors())}
                )
                continue
            candidates.append((row_number, lead_data))
    except csv.Error as exc:
        errors.append({"row": int(summary["total_rows"]) + 2, "error": f"Invalid CSV: {exc}"})
        return summary

    if not candidates:
        return summary

    candidate_pairs = {
        (str(data["company_name"]).lower(), str(data["contact_name"]).lower())
        for _, data in candidates
    }
    existing_pairs = set(
        db.execute(
            select(func.lower(Lead.company_name), func.lower(Lead.contact_name)).where(
                tuple_(func.lower(Lead.company_name), func.lower(Lead.contact_name)).in_(
                    sorted(candidate_pairs)
                )
            )
        ).tuples()
    )

    seen_pairs = set(existing_pairs)
    insert_rows: list[dict[str, object]] = []
    for row_number, data in candidates:
        pair = (str(data["company_name"]).lower(), str(data["contact_name"]).lower())
        if pair in seen_pairs:
            summary["duplicates_skipped"] = int(summary["duplicates_skipped"]) + 1
            if pair not in existing_pairs:
                errors.append({"row": row_number, "error": "Duplicate lead in this CSV; skipped."})
            continue
        seen_pairs.add(pair)
        insert_rows.append(data)

    if insert_rows:
        db.bulk_insert_mappings(Lead, insert_rows)
        db.commit()
        summary["inserted"] = len(insert_rows)
    return summary


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead(lead_id: int, db: DatabaseSession) -> Lead:
    """Retrieve one lead or return 404 when it does not exist."""
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead


@router.put("/{lead_id}", response_model=LeadResponse)
def update_lead(lead_id: int, payload: LeadUpdate, db: DatabaseSession) -> Lead:
    """Update supplied lead fields after validating the lifecycle stage."""
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(lead, field, value)
    db.commit()
    db.refresh(lead)
    return lead


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(lead_id: int, db: DatabaseSession) -> Response:
    """Permanently remove a lead and return 404 if it is absent."""
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    db.delete(lead)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
