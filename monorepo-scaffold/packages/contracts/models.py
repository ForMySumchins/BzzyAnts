from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class LicenseRightsTag(str, Enum):
    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"
    PUBLIC_OFFICIAL = "PUBLIC_OFFICIAL"
    VERIFIED_LICENSED = "VERIFIED_LICENSED"

class OperationalStatus(str, Enum):
    ACTIVE_VERIFIED = "ACTIVE_VERIFIED"
    LIKELY_ACTIVE = "LIKELY_ACTIVE"
    UNKNOWN = "UNKNOWN"
    POSSIBLY_CLOSED = "POSSIBLY_CLOSED"
    CONFIRMED_CLOSED = "CONFIRMED_CLOSED"
    NEEDS_REVIEW = "NEEDS_REVIEW"

class OfferFamily(str, Enum):
    WEBSITE_CREATION = "website_creation"
    WEBSITE_CONTACT_REPAIR = "website_contact_repair"
    LOGO_BRAND_KIT = "logo_brand_kit"
    PRINT_DESIGN_ASSETS = "print_design_assets"
    SOCIAL_TEMPLATES = "social_templates"
    BOOKING_WORKFLOW_AUTOMATION = "booking_workflow_automation"

class DiscoveryLane(str, Enum):
    CONFIRMED_REQUEST = "confirmed_request"
    VERIFIED_FUNCTIONAL_PROBLEM = "verified_functional_problem"
    EVENT_LINKED_CREATIVE = "event_linked_creative"

class OfferQualificationStatus(str, Enum):
    OFFER_CANDIDATE = "OFFER_CANDIDATE"
    CONFIRMED_SCOPE = "CONFIRMED_SCOPE"
    REQUIRES_DISCOVERY = "REQUIRES_DISCOVERY"
    WITHHELD_NOT_FIT = "WITHHELD_NOT_FIT"
    REVIEW = "REVIEW"

class HeatScoreContract(BaseModel):
    score: float = Field(ge=0.0, le=10.0)
    tier: str
    need: float = Field(ge=0.0, le=10.0)
    readiness: float = Field(ge=0.0, le=10.0)
    value: float = Field(ge=0.0, le=10.0)
    confidence: float = Field(ge=0.0, le=10.0)
    category_key: str = "other"
    confidence_gated: bool = False
    disqualified: bool = False
    gated_reason: Optional[str] = None

class OfferAssessmentContract(BaseModel):
    offer_family: OfferFamily
    lane: DiscoveryLane
    status: OfferQualificationStatus
    operator_explanation: str
    reason_codes: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)
    next_verification_step: str

class SourceRecord(BaseModel):
    source_id: str
    adapter_type: str
    jurisdiction_id: str
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    record_effective_at: Optional[datetime] = None
    raw_sha256: str
    license_rights_tag: LicenseRightsTag = LicenseRightsTag.PUBLIC_OFFICIAL
    raw_payload: Dict[str, Any] = Field(default_factory=dict)

class Site(BaseModel):
    site_id: str
    apn: Optional[str] = None
    street_address: str
    postal_city: str
    jurisdiction_id: str
    latitude: float
    longitude: float
    h3_index: str
    land_use_code: Optional[str] = None

class Signal(BaseModel):
    signal_id: str
    signal_type: str
    source_record_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    observed_at: datetime = Field(default_factory=datetime.utcnow)
    details: Dict[str, Any] = Field(default_factory=dict)

class Business(BaseModel):
    business_id: str
    legal_name: str
    dba_name: Optional[str] = None
    verified_phone: Optional[str] = None
    primary_domain: Optional[str] = None
    status: OperationalStatus = OperationalStatus.UNKNOWN
    ca_sos_id: Optional[str] = None
    cslb_license_number: Optional[str] = None
    is_home_based: bool = False
    franchise_restricted: bool = False
    linked_site_ids: List[str] = Field(default_factory=list)

class Opportunity(BaseModel):
    opportunity_id: str
    business_id: Optional[str] = None
    site_id: str
    composite_score: float = Field(ge=0.0, le=100.0)
    score_breakdown: Dict[str, float] = Field(default_factory=dict)
    heat_score: Optional[HeatScoreContract] = None
    offer_assessments: List[OfferAssessmentContract] = Field(default_factory=list)
    active_signals: List[Signal] = Field(default_factory=list)
    status: str = "OPEN_SCOUTED"
    assigned_operator_id: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class FieldObservation(BaseModel):
    observation_id: str
    opportunity_id: str
    operator_id: str
    client_idempotency_key: str
    captured_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None
    media_sha256: Optional[str] = None
    media_url: Optional[str] = None
    sync_status: str = "SYNCED"
    mantis_eye_extracted: Optional[Dict[str, Any]] = None

class Package(BaseModel):
    package_id: str
    name: str
    category: str
    description: str
    estimated_setup_hours: float
    deliverable_type: str

class PackageSuggestion(BaseModel):
    suggestion_id: str
    opportunity_id: str
    package_id: str
    candidate_reason: str
    evidence_signal_ids: List[str] = Field(default_factory=list)
    status: str = "CANDIDATE_PROPOSAL"

class Coverage(BaseModel):
    h3_index: str
    jurisdiction_id: str
