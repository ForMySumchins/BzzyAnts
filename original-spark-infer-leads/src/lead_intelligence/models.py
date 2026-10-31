"""Core data models and contracts for BZZY Lead Intelligence.

Follows the canonical minimum data contracts specified in Master Directive:
TASK_ID: BZZY-LEADVERIFY-001 | PROJECT: BZZY-SOLUTIONS
Merged with BZZY Ants Lead Engine Validity Audit (2026-10-19) Packets P1-P5.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


class SourceLicenseStatus(str, Enum):
    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"
    VERIFIED_LICENSED = "VERIFIED_LICENSED"
    UNVERIFIED_SCRAPED = "UNVERIFIED_SCRAPED"
    RESTRICTED = "RESTRICTED"


class OperationalStatus(str, Enum):
    ACTIVE_VERIFIED = "ACTIVE_VERIFIED"
    LIKELY_ACTIVE = "LIKELY_ACTIVE"
    UNKNOWN = "UNKNOWN"
    POSSIBLY_CLOSED = "POSSIBLY_CLOSED"
    CONFIRMED_CLOSED = "CONFIRMED_CLOSED"


class DigitalPresenceGap(str, Enum):
    NO_WEBSITE = "NO_WEBSITE"
    OUTDATED_WEBSITE = "OUTDATED_WEBSITE"
    NO_BOOKING_OR_CONTACT = "NO_BOOKING_OR_CONTACT"
    DORMANT_SOCIAL = "DORMANT_SOCIAL"
    NO_SSL_OR_INSECURE = "NO_SSL_OR_INSECURE"
    UNRESPONSIVE_DOMAIN = "UNRESPONSIVE_DOMAIN"


class OutreachReadiness(str, Enum):
    READY = "READY"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    SUPPRESSED = "SUPPRESSED"
    INELIGIBLE = "INELIGIBLE"


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


@dataclass
class HeatScoreResult:
    score: float
    tier: str
    need: float
    readiness: float
    value: float
    confidence: float
    category_key: str = "other"
    confidence_gated: bool = False
    disqualified: bool = False
    gated_reason: Optional[str] = None


@dataclass
class OfferAssessment:
    offer_family: OfferFamily
    lane: DiscoveryLane
    status: OfferQualificationStatus
    operator_explanation: str
    reason_codes: List[str] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)
    next_verification_step: str = "Verify decision-maker contact and channel preference."


@dataclass
class AddressComponents:
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    country: Optional[str] = "US"


@dataclass
class SourceReference:
    source_name: str
    actor_id: Optional[str] = None
    raw_id: Optional[str] = None
    observed_at: Optional[str] = None
    raw_hash: Optional[str] = None


@dataclass
class Lead:
    internal_lead_id: str
    name: str
    category: str
    source_refs: List[SourceReference] = field(default_factory=list)
    address_components: Optional[AddressComponents] = None
    phone: Optional[str] = None
    emails: List[str] = field(default_factory=list)
    website_candidates: List[str] = field(default_factory=list)
    social_accounts: List[str] = field(default_factory=list)
    place_id: Optional[str] = None
    import_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    source_license_status: SourceLicenseStatus = SourceLicenseStatus.SYNTHETIC_FIXTURE
    state: Optional[str] = None
    city: Optional[str] = None
    zip: Optional[str] = None
    is_placeholder: bool = False
    is_home_based: bool = False
    franchise_restricted: bool = False
    validation_errors: List[str] = field(default_factory=list)


@dataclass
class Evidence:
    evidence_id: str
    lead_id: str
    signal_type: str
    observed_value: Any
    observed_at: Optional[str] = None
    source_url: Optional[str] = None
    collection_method: str = "OFFLINE_FIXTURE"
    reliability_class: str = "UNVERIFIED"
    expires_at: Optional[str] = None
    parser_version: str = "1.0.0"
    raw_reference_hash: Optional[str] = None
    confidence: float = 0.5
    conflicts_with: List[str] = field(default_factory=list)


@dataclass
class Assessment:
    lead_id: str
    business_status: OperationalStatus
    digital_gaps: List[DigitalPresenceGap] = field(default_factory=list)
    outreach_readiness: OutreachReadiness = OutreachReadiness.NEEDS_REVIEW
    opportunity_score: Optional[float] = None
    reason_codes: List[str] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)
    checked_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    next_review_at: Optional[str] = None
    needs_human_review: bool = False
    suppressed: bool = False
    decision_version: str = "2.0.0-audited"
    heat_score: Optional[HeatScoreResult] = None
    offer_assessments: List[OfferAssessment] = field(default_factory=list)
