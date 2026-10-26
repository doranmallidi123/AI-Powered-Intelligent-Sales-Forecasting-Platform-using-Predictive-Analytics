"""Request and response schemas for lead management."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LeadStatus = Literal["new", "contacted", "qualified", "closed"]


class LeadBase(BaseModel):
    """Shared lead fields used when creating or updating a lead."""

    company_name: str = Field(min_length=1, max_length=255)
    industry: str = Field(min_length=1, max_length=255)
    contact_name: str = Field(min_length=1, max_length=255)
    lead_status: LeadStatus = "new"
    tech_stack: str | None = None
    funding_stage: str | None = Field(default=None, max_length=100)


class LeadCreate(LeadBase):
    """Fields required to create a lead."""


class LeadUpdate(BaseModel):
    """Optional fields accepted when updating a lead."""

    company_name: str | None = Field(default=None, min_length=1, max_length=255)
    industry: str | None = Field(default=None, min_length=1, max_length=255)
    contact_name: str | None = Field(default=None, min_length=1, max_length=255)
    lead_status: LeadStatus | None = None
    tech_stack: str | None = None
    funding_stage: str | None = Field(default=None, max_length=100)


class LeadResponse(LeadBase):
    """Lead representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    lead_id: int
    created_at: datetime
    updated_at: datetime
