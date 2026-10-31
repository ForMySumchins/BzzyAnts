"""Conservative status, gated Heat Score, and 6-Offer qualification engine.

Merges Master Directive (BZZY-LEADVERIFY-001) with BZZY Ants Lead Engine Validity
Audit (2026-10-19) Packets P1-P5:
- Enforces hard disqualifier gates (Identity, Activity, Franchise Authority) BEFORE
  computing Heat Score dimensions so closed or restricted businesses cannot be
  compensated into 'hot' or 'blazing' tiers (Fixes F02).
- Routes low confidence (C < 5.0) to 'needs_review' rather than forcing 'warm' on
  zero-score leads (Fixes F03).
- Parses Wappalyzer/detector category objects and strings safely, preserving
  UNKNOWN state on empty responses (Fixes F05).
- Evaluates the 6 BZZY Offer Families across 3 discovery lanes (confirmed request,
  verified functional problem, event-linked creative) with truthful operator
  explanation strings (Fixes F08, P2, P4).
"""

from typing import List, Optional, Dict, Any, Tuple
from ..models import (
    Lead,
    Evidence,
    Assessment,
    OperationalStatus,
    DigitalPresenceGap,
    OutreachReadiness,
    OfferFamily,
    DiscoveryLane,
    OfferQualificationStatus,
    HeatScoreResult,
    OfferAssessment,
)

# Section 2.3 Category Weight Table (Need, Readiness, Value)
CATEGORY_WEIGHTS: Dict[str, Tuple[float, float, float]] = {
    "restaurant": (0.45, 0.35, 0.20),
    "hvac": (0.30, 0.30, 0.40),
    "salon_spa": (0.35, 0.40, 0.25),
    "medical_dental": (0.30, 0.25, 0.45),
    "legal_professional": (0.30, 0.25, 0.45),
    "retail": (0.45, 0.30, 0.25),
    "gym_fitness": (0.35, 0.35, 0.30),
    "auto_mechanic": (0.35, 0.30, 0.35),
    "contractor": (0.30, 0.30, 0.40),
    "bar_nightlife": (0.40, 0.35, 0.25),
    "skate_action": (0.35, 0.40, 0.25),
    "creative_agency": (0.35, 0.35, 0.30),
    "informal": (0.30, 0.50, 0.20),
    "other": (0.40, 0.30, 0.30),
}


def resolve_category_key(raw_category: Optional[str]) -> str:
    """Maps a human-readable category string onto the canonical weight table key."""
    if not raw_category:
        return "other"
    c = raw_category.lower().strip()
    if c in CATEGORY_WEIGHTS:
        return c
    if any(k in c for k in ("hvac", "air conditioning", "heating")):
        return "hvac"
    if any(k in c for k in ("plumb", "electric", "roof", "restoration", "contractor", "landscap", "construction")):
        return "contractor"
    if any(k in c for k in ("auto", "mechanic", "tire", "body shop", "smog")):
        return "auto_mechanic"
    if any(k in c for k in ("medical", "dental", "dentist", "clinic", "chiropract", "optometr")):
        return "medical_dental"
    if any(k in c for k in ("restaurant", "cafe", "bakery", "taco", "pizza", "diner", "food")):
        return "restaurant"
    if any(k in c for k in ("salon", "spa", "barber", "nail", "beauty")):
        return "salon_spa"
    if any(k in c for k in ("legal", "law", "attorney", "CPA", "accountant")):
        return "legal_professional"
    if any(k in c for k in ("gym", "fitness", "yoga", "pilates")):
        return "gym_fitness"
    if any(k in c for k in ("bar", "nightlife", "lounge", "brewery")):
        return "bar_nightlife"
    if any(k in c for k in ("retail", "shop", "store", "boutique")):
        return "retail"
    return "other"


def clamp_dimension(val: float) -> float:
    return max(0.0, min(10.0, float(val)))


def compute_gated_heat_score(
    need: float,
    readiness: float,
    value: float,
    confidence: float,
    category: str = "other",
    is_closed: bool = False,
    is_franchise_restricted: bool = False,
    is_suppressed: bool = False,
) -> HeatScoreResult:
    """Computes the audited, gate-protected Heat Score (Fixes F02, F03)."""
    n = clamp_dimension(need)
    r = clamp_dimension(readiness)
    v = clamp_dimension(value)
    c = clamp_dimension(confidence)
    cat_key = resolve_category_key(category)
    w_n, w_r, w_v = CATEGORY_WEIGHTS[cat_key]

    if is_closed or is_suppressed:
        return HeatScoreResult(
            score=0.0,
            tier="withheld",
            need=n,
            readiness=r,
            value=v,
            confidence=c,
            category_key=cat_key,
            confidence_gated=False,
            disqualified=True,
            gated_reason="DISQUALIFIED_CLOSED_OR_SUPPRESSED",
        )

    if is_franchise_restricted:
        return HeatScoreResult(
            score=0.0,
            tier="withheld",
            need=n,
            readiness=r,
            value=v,
            confidence=c,
            category_key=cat_key,
            confidence_gated=False,
            disqualified=True,
            gated_reason="DISQUALIFIED_FRANCHISE_AUTHORITY_RESTRICTED",
        )

    raw_score = round((c / 10.0) * (w_n * n + w_r * r + w_v * v), 6)

    # Fix F03: Low confidence (< 5.0) routes to needs_review instead of forced 'warm'
    if c < 5.0:
        return HeatScoreResult(
            score=raw_score,
            tier="needs_review",
            need=n,
            readiness=r,
            value=v,
            confidence=c,
            category_key=cat_key,
            confidence_gated=True,
            disqualified=False,
            gated_reason="GATE_LOW_CONFIDENCE_REQUIRES_VERIFICATION",
        )

    # Fix F02: Zero readiness cannot be compensated into 'hot' or 'blazing'
    if r <= 0.0:
        capped_tier = "warm" if raw_score >= 3.0 else "cold"
        return HeatScoreResult(
            score=raw_score,
            tier=capped_tier,
            need=n,
            readiness=r,
            value=v,
            confidence=c,
            category_key=cat_key,
            confidence_gated=False,
            disqualified=False,
            gated_reason="GATE_ZERO_READINESS_NON_COMPENSATORY_CAP",
        )

    if raw_score >= 7.0:
        tier = "blazing"
    elif raw_score >= 5.0:
        tier = "hot"
    elif raw_score >= 3.0:
        tier = "warm"
    else:
        tier = "cold"

    return HeatScoreResult(
        score=raw_score,
        tier=tier,
        need=n,
        readiness=r,
        value=v,
        confidence=c,
        category_key=cat_key,
        confidence_gated=False,
        disqualified=False,
        gated_reason=None,
    )


def parse_technology_signals(detector_response: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Object-safe parser for Wappalyzer/technology detector payloads (Fixes F05).

    Supports both string category names and documented Wappalyzer category objects
    ({'id': 10, 'name': 'Analytics', 'slug': 'analytics'}). Preserves UNKNOWN state
    on empty or missing payloads instead of falsely asserting dark_advertiser_confirmed.
    """
    if not detector_response or not isinstance(detector_response, dict):
        return {
            "has_analytics": None,
            "has_ad_pixel": None,
            "dark_advertiser_confirmed": False,
            "observation_state": "UNKNOWN",
        }

    techs = detector_response.get("technologies")
    if techs is None or not isinstance(techs, list) or len(techs) == 0:
        return {
            "has_analytics": None,
            "has_ad_pixel": None,
            "dark_advertiser_confirmed": False,
            "observation_state": "UNKNOWN",
        }

    category_names = set()
    for tech in techs:
        if not isinstance(tech, dict):
            continue
        cats = tech.get("categories", [])
        for cat in cats:
            if isinstance(cat, str):
                category_names.add(cat.strip().lower())
            elif isinstance(cat, dict):
                name = cat.get("name") or cat.get("slug")
                if isinstance(name, str):
                    category_names.add(name.strip().lower())

    has_analytics = "analytics" in category_names
    has_ad_pixel = any(k in category_names for k in ("advertising networks", "advertising", "remarketing", "ad-network"))

    return {
        "has_analytics": has_analytics,
        "has_ad_pixel": has_ad_pixel,
        "dark_advertiser_confirmed": bool(has_ad_pixel and not has_analytics),
        "observation_state": "OBSERVED",
    }


def qualify_offers_for_lead(
    lead: Lead,
    evidence_list: List[Evidence],
    business_status: OperationalStatus,
    digital_gaps: List[DigitalPresenceGap],
) -> List[OfferAssessment]:
    """Evaluates the 6 BZZY Offer Families across 3 discovery lanes (Packets P2, P4)."""
    if lead.is_placeholder or business_status == OperationalStatus.CONFIRMED_CLOSED:
        return [
            OfferAssessment(
                offer_family=OfferFamily.WEBSITE_CREATION,
                lane=DiscoveryLane.VERIFIED_FUNCTIONAL_PROBLEM,
                status=OfferQualificationStatus.WITHHELD_NOT_FIT,
                operator_explanation="Withheld: Business is confirmed closed or marked as a synthetic placeholder.",
                reason_codes=["WITHHELD_CLOSED_OR_PLACEHOLDER"],
                evidence_ids=[e.evidence_id for e in evidence_list],
                unknowns=[],
                next_verification_step="None — do not contact.",
            )
        ]

    assessments: List[OfferAssessment] = []
    ev_by_type: Dict[str, List[Evidence]] = {}
    for ev in evidence_list:
        ev_by_type.setdefault(ev.signal_type, []).append(ev)

    has_contact = bool(lead.phone or lead.emails)
    common_unknowns = ["buyer_authority", "available_budget", "owner_interest"]
    if not has_contact:
        common_unknowns.append("verified_decision_maker_contact")

    # 1. Website Creation
    if DigitalPresenceGap.NO_WEBSITE in digital_gaps or "OWNER_REQUEST_WEBSITE" in ev_by_type:
        if lead.franchise_restricted:
            assessments.append(
                OfferAssessment(
                    offer_family=OfferFamily.WEBSITE_CREATION,
                    lane=DiscoveryLane.VERIFIED_FUNCTIONAL_PROBLEM,
                    status=OfferQualificationStatus.WITHHELD_NOT_FIT,
                    operator_explanation="Withheld: Franchise restrictions prevent local website deployment.",
                    reason_codes=["FRANCHISE_WEBSITE_RESTRICTED"],
                    evidence_ids=[e.evidence_id for e in evidence_list],
                    unknowns=common_unknowns,
                    next_verification_step="Check if local print or collateral permissions exist separately.",
                )
            )
        elif "SOCIAL_EFFECTIVE_CHANNEL" in ev_by_type and "OWNER_REQUEST_WEBSITE" not in ev_by_type:
            assessments.append(
                OfferAssessment(
                    offer_family=OfferFamily.WEBSITE_CREATION,
                    lane=DiscoveryLane.VERIFIED_FUNCTIONAL_PROBLEM,
                    status=OfferQualificationStatus.REQUIRES_DISCOVERY,
                    operator_explanation=(
                        "Requires discovery: Business operates an active social sales channel without a standalone "
                        "domain. Do not assume a website rebuild is needed without confirming owner channel preference."
                    ),
                    reason_codes=["SOCIAL_ONLY_WORKING_CHANNEL"],
                    evidence_ids=[e.evidence_id for e in evidence_list],
                    unknowns=common_unknowns + ["channel_preference"],
                    next_verification_step="Verify whether current social booking channel meets customer demand.",
                )
            )
        else:
            lane = (
                DiscoveryLane.CONFIRMED_REQUEST
                if "OWNER_REQUEST_WEBSITE" in ev_by_type
                else DiscoveryLane.VERIFIED_FUNCTIONAL_PROBLEM
            )
            status = (
                OfferQualificationStatus.OFFER_CANDIDATE
                if business_status in (OperationalStatus.ACTIVE_VERIFIED, OperationalStatus.LIKELY_ACTIVE)
                else OfferQualificationStatus.REVIEW
            )
            assessments.append(
                OfferAssessment(
                    offer_family=OfferFamily.WEBSITE_CREATION,
                    lane=lane,
                    status=status,
                    operator_explanation=(
                        "Candidate: website creation. A dedicated mobile starter site may address the absent "
                        "web presence. Current channel preference, domain ownership, and budget are unknown."
                    ),
                    reason_codes=["GAP_NO_DEDICATED_WEBSITE"],
                    evidence_ids=[e.evidence_id for e in evidence_list],
                    unknowns=common_unknowns + ["domain_ownership"],
                    next_verification_step="Confirm website search scope and owner contact path.",
                )
            )

    # 2. Website / Contact-Path Repair
    if (
        DigitalPresenceGap.UNRESPONSIVE_DOMAIN in digital_gaps
        or DigitalPresenceGap.NO_BOOKING_OR_CONTACT in digital_gaps
        or "BROKEN_CONTACT_PATH" in ev_by_type
    ):
        assessments.append(
            OfferAssessment(
                offer_family=OfferFamily.WEBSITE_CONTACT_REPAIR,
                lane=DiscoveryLane.VERIFIED_FUNCTIONAL_PROBLEM,
                status=OfferQualificationStatus.OFFER_CANDIDATE,
                operator_explanation=(
                    "Candidate: mobile contact/website repair. The matched business website or contact path "
                    "failed in documented checks. Buyer authority, budget, and revenue impact are unknown."
                ),
                reason_codes=["REPRODUCED_CONTACT_OR_DOMAIN_FAILURE"],
                evidence_ids=[e.evidence_id for e in evidence_list],
                unknowns=common_unknowns + ["site_stack_access"],
                next_verification_step="Repeat read-only check and confirm intended contact route.",
            )
        )

    # 3. Logo / Basic Brand Kit (Creative lane — requires request or verified launch/rebrand event, NOT site defect)
    if "OWNER_REQUEST_LOGO" in ev_by_type or "VERIFIED_LAUNCH_OR_REBRAND" in ev_by_type:
        lane = (
            DiscoveryLane.CONFIRMED_REQUEST
            if "OWNER_REQUEST_LOGO" in ev_by_type
            else DiscoveryLane.EVENT_LINKED_CREATIVE
        )
        assessments.append(
            OfferAssessment(
                offer_family=OfferFamily.LOGO_BRAND_KIT,
                lane=lane,
                status=OfferQualificationStatus.OFFER_CANDIDATE,
                operator_explanation=(
                    "Candidate: logo/brand kit. Verified launch, rebrand, or explicit owner request supports "
                    "brand asset discovery without requiring a website defect."
                ),
                reason_codes=["CREATIVE_LAUNCH_OR_BRAND_REQUEST"],
                evidence_ids=[e.evidence_id for e in evidence_list],
                unknowns=common_unknowns + ["existing_brand_rights"],
                next_verification_step="Confirm creative brief and whether a new mark or vectorization is wanted.",
            )
        )

    # 4. Print / Design Assets (Flyer, service sheet, sticker for event or launch)
    if (
        "OWNER_REQUEST_PRINT" in ev_by_type
        or "VERIFIED_LAUNCH_OR_REBRAND" in ev_by_type
        or "UPCOMING_LOCAL_EVENT" in ev_by_type
    ):
        lane = (
            DiscoveryLane.CONFIRMED_REQUEST
            if "OWNER_REQUEST_PRINT" in ev_by_type
            else DiscoveryLane.EVENT_LINKED_CREATIVE
        )
        assessments.append(
            OfferAssessment(
                offer_family=OfferFamily.PRINT_DESIGN_ASSETS,
                lane=lane,
                status=OfferQualificationStatus.OFFER_CANDIDATE,
                operator_explanation=(
                    "Candidate: print/design assets. Announced launch, event, or owner request supports a "
                    "flyer, service sheet, or QR sticker package."
                ),
                reason_codes=["EVENT_OR_REQUEST_PRINT_ASSET"],
                evidence_ids=[e.evidence_id for e in evidence_list],
                unknowns=common_unknowns + ["print_quantities_and_deadline"],
                next_verification_step="Verify distribution use case, dimensions, and deadline.",
            )
        )

    # 5. Social Templates
    if DigitalPresenceGap.DORMANT_SOCIAL in digital_gaps or "RECURRING_CONTENT_NEED" in ev_by_type:
        assessments.append(
            OfferAssessment(
                offer_family=OfferFamily.SOCIAL_TEMPLATES,
                lane=DiscoveryLane.EVENT_LINKED_CREATIVE,
                status=OfferQualificationStatus.REQUIRES_DISCOVERY,
                operator_explanation=(
                    "Requires discovery: social templates. Dormant social channels or recurring campaign needs "
                    "observed; verify whether owner actively uses social channels before pitching templates."
                ),
                reason_codes=["SOCIAL_TEMPLATE_CANDIDATE"],
                evidence_ids=[e.evidence_id for e in evidence_list],
                unknowns=common_unknowns + ["social_posting_workflow"],
                next_verification_step="Ask for actual recurring post formats or campaign schedule.",
            )
        )

    # 6. Booking / Workflow Automation (CallShield / missed-call triage)
    if "MISSED_CALL_COMPLAINTS" in ev_by_type or "OWNER_REQUEST_AUTOMATION" in ev_by_type:
        assessments.append(
            OfferAssessment(
                offer_family=OfferFamily.BOOKING_WORKFLOW_AUTOMATION,
                lane=(
                    DiscoveryLane.CONFIRMED_REQUEST
                    if "OWNER_REQUEST_AUTOMATION" in ev_by_type
                    else DiscoveryLane.VERIFIED_FUNCTIONAL_PROBLEM
                ),
                status=OfferQualificationStatus.OFFER_CANDIDATE,
                operator_explanation=(
                    "Candidate: booking/missed-call workflow automation. Concrete call-handling or scheduling "
                    "friction observed; technical integration access and compliance scope require verification."
                ),
                reason_codes=["WORKFLOW_OR_CALL_TRIAGE_CANDIDATE"],
                evidence_ids=[e.evidence_id for e in evidence_list],
                unknowns=common_unknowns + ["phone_routing_stack"],
                next_verification_step="Conduct technical discovery on current phone/booking workflow.",
            )
        )

    return assessments


def infer_lead_status(lead: Lead, evidence_list: List[Evidence]) -> Assessment:
    """Produces conservative operational status, digital presence gaps, gated Heat Score, and 6-Offer assessments."""
    reason_codes: List[str] = []
    gaps: List[DigitalPresenceGap] = []
    evidence_ids = [e.evidence_id for e in evidence_list]

    # Check for suppression / opt-out / placeholder
    if lead.is_placeholder:
        heat = compute_gated_heat_score(
            need=0.0,
            readiness=0.0,
            value=0.0,
            confidence=0.0,
            category=lead.category,
            is_suppressed=True,
        )
        return Assessment(
            lead_id=lead.internal_lead_id,
            business_status=OperationalStatus.UNKNOWN,
            digital_gaps=[DigitalPresenceGap.NO_WEBSITE],
            outreach_readiness=OutreachReadiness.INELIGIBLE,
            opportunity_score=0.0,
            reason_codes=["REJECTED_PLACEHOLDER_OR_SYNTHETIC_TEST"],
            evidence_ids=evidence_ids,
            needs_human_review=False,
            suppressed=True,
            heat_score=heat,
            offer_assessments=[],
        )

    # Analyze digital gaps (Deduplicated by underlying problem per F06)
    has_website_omission = not lead.website_candidates
    resolved_website_from_evidence = any(
        ev.signal_type == "RESOLVED_OFFICIAL_DOMAIN" for ev in evidence_list
    )
    if has_website_omission and not resolved_website_from_evidence:
        gaps.append(DigitalPresenceGap.NO_WEBSITE)
        reason_codes.append("GAP_NO_DEDICATED_WEBSITE")

    # Analyze evidence signals
    has_recent_activity = False
    has_stale_marketing = False
    has_authoritative_closure = False
    has_unverified_closure_claim = False
    has_active_license_or_contractor_signal = False
    has_creative_or_launch_event = False
    has_owner_request = False

    for ev in evidence_list:
        if ev.signal_type == "RECENT_CUSTOMER_REVIEW":
            has_recent_activity = True
            reason_codes.append("SIGNAL_RECENT_CUSTOMER_REVIEW")
        elif ev.signal_type == "ACTIVE_STATE_LICENSE":
            has_active_license_or_contractor_signal = True
            reason_codes.append("SIGNAL_ACTIVE_STATE_LICENSE")
        elif ev.signal_type == "SOCIAL_DORMANT":
            has_stale_marketing = True
            if DigitalPresenceGap.DORMANT_SOCIAL not in gaps:
                gaps.append(DigitalPresenceGap.DORMANT_SOCIAL)
            reason_codes.append("GAP_DORMANT_SOCIAL_CHANNELS")
        elif ev.signal_type == "OFFICIAL_CLOSURE_NOTICE":
            has_authoritative_closure = True
            reason_codes.append("SIGNAL_OFFICIAL_CLOSURE_NOTICE")
        elif ev.signal_type == "UNVERIFIED_DIRECTORY_CLOSED":
            has_unverified_closure_claim = True
            reason_codes.append("SIGNAL_DIRECTORY_MARKED_CLOSED")
        elif ev.signal_type == "DEAD_DOMAIN":
            if DigitalPresenceGap.UNRESPONSIVE_DOMAIN not in gaps:
                gaps.append(DigitalPresenceGap.UNRESPONSIVE_DOMAIN)
            reason_codes.append("GAP_UNRESPONSIVE_OR_EXPIRED_DOMAIN")
        elif ev.signal_type == "BROKEN_CONTACT_PATH":
            if DigitalPresenceGap.NO_BOOKING_OR_CONTACT not in gaps:
                gaps.append(DigitalPresenceGap.NO_BOOKING_OR_CONTACT)
            reason_codes.append("GAP_BROKEN_CONTACT_OR_BOOKING_PATH")
        elif ev.signal_type in ("VERIFIED_LAUNCH_OR_REBRAND", "UPCOMING_LOCAL_EVENT"):
            has_creative_or_launch_event = True
            has_recent_activity = True
            reason_codes.append(f"SIGNAL_{ev.signal_type}")
        elif ev.signal_type.startswith("OWNER_REQUEST_"):
            has_owner_request = True
            has_recent_activity = True
            reason_codes.append(f"SIGNAL_{ev.signal_type}")

    # Fix F07: Home-based businesses are NOT penalized as closed/inactive
    if lead.is_home_based:
        reason_codes.append("CONTEXT_HOME_BASED_SERVICE_AREA_BUSINESS")

    # Operational status determination
    if has_authoritative_closure:
        status = OperationalStatus.CONFIRMED_CLOSED
        readiness = OutreachReadiness.INELIGIBLE
        score = 0.0
        needs_review = False
        need_dim, ready_dim, val_dim, conf_dim = 0.0, 0.0, 0.0, 10.0
    elif has_unverified_closure_claim and (has_recent_activity or has_active_license_or_contractor_signal):
        status = OperationalStatus.LIKELY_ACTIVE
        readiness = OutreachReadiness.NEEDS_REVIEW
        reason_codes.append("CONFLICT_DIRECTORY_CLOSED_VS_RECENT_ACTIVE_EVIDENCE")
        score = 45.0
        needs_review = True
        need_dim, ready_dim, val_dim, conf_dim = 6.0, 5.0, 6.0, 4.5
    elif has_unverified_closure_claim:
        status = OperationalStatus.POSSIBLY_CLOSED
        readiness = OutreachReadiness.NEEDS_REVIEW
        score = 15.0
        needs_review = True
        need_dim, ready_dim, val_dim, conf_dim = 3.0, 2.0, 4.0, 3.0
    elif has_recent_activity or has_active_license_or_contractor_signal:
        status = (
            OperationalStatus.ACTIVE_VERIFIED
            if has_active_license_or_contractor_signal
            else OperationalStatus.LIKELY_ACTIVE
        )
        readiness = OutreachReadiness.READY if (lead.phone or lead.emails) else OutreachReadiness.NEEDS_REVIEW
        score = 85.0 if DigitalPresenceGap.NO_WEBSITE in gaps else 65.0
        needs_review = readiness == OutreachReadiness.NEEDS_REVIEW
        need_dim = 8.5 if DigitalPresenceGap.NO_WEBSITE in gaps else (7.5 if gaps or has_creative_or_launch_event or has_owner_request else 4.0)
        ready_dim = 8.0 if has_owner_request else (6.5 if (lead.phone or lead.emails) else 3.0)
        val_dim = 7.5
        conf_dim = 8.5 if status == OperationalStatus.ACTIVE_VERIFIED else 7.0
    else:
        status = OperationalStatus.UNKNOWN
        readiness = OutreachReadiness.NEEDS_REVIEW
        score = 30.0
        needs_review = True
        need_dim = 5.0 if gaps else 3.0
        ready_dim = 3.0
        val_dim = 5.0
        conf_dim = 4.0

    heat = compute_gated_heat_score(
        need=need_dim,
        readiness=ready_dim,
        value=val_dim,
        confidence=conf_dim,
        category=lead.category,
        is_closed=(status == OperationalStatus.CONFIRMED_CLOSED),
        is_franchise_restricted=lead.franchise_restricted,
        is_suppressed=False,
    )

    offer_assessments = qualify_offers_for_lead(
        lead=lead,
        evidence_list=evidence_list,
        business_status=status,
        digital_gaps=gaps,
    )

    return Assessment(
        lead_id=lead.internal_lead_id,
        business_status=status,
        digital_gaps=gaps,
        outreach_readiness=readiness,
        opportunity_score=score,
        reason_codes=reason_codes,
        evidence_ids=evidence_ids,
        needs_human_review=needs_review,
        suppressed=False,
        heat_score=heat,
        offer_assessments=offer_assessments,
    )
