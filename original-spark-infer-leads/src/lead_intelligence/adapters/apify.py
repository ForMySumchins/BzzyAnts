"""Offline adapters for normalizing Apify actor exports.

Handles:
1. SOURCE A: businesses-without-websites-leads-scraper-google-maps
2. SOURCE B: old-websites-businesses-leads
3. Generic CSV/JSON lead fixtures

Enforces schema normalization, raw-hash integrity, placeholder detection,
and offline execution without paid API calls.
"""

import hashlib
import json
import re
from typing import Dict, Any, List, Optional
from ..models import (
    Lead,
    AddressComponents,
    SourceReference,
    SourceLicenseStatus,
)


def compute_sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def normalize_phone(raw_phone: Optional[str]) -> Optional[str]:
    if not raw_phone:
        return None
    cleaned = re.sub(r"[^\d+]", "", str(raw_phone).strip())
    if not cleaned:
        return None
    # Detect synthetic 555-01xx or 555 numbers
    digits_only = re.sub(r"[^\d]", "", cleaned)
    if "555" in digits_only:
        # Check if it matches typical TV/test pattern 555-0100 through 555-0199 or standard 555
        if re.search(r"555\d{4}$", digits_only):
            return None  # Disallowed synthetic placeholder for real outreach
    return cleaned


def is_placeholder_lead(name: str, phone: Optional[str], emails: List[str]) -> bool:
    """Detects test records, generic labels, or placeholder leads."""
    name_lower = name.lower().strip()
    if any(term in name_lower for term in ["test business", "sample company", "demo llc", "placeholder", "foo bar"]):
        return True
    if not phone and not emails:
        # Lacks any direct communication channel
        pass
    return False


class ApifyNoWebsiteAdapter:
    """Normalizer for Apify actor: xmiso_scrapers/businesses-without-websites-leads-scraper-google-maps."""

    ACTOR_ID = "xmiso_scrapers/businesses-without-websites-leads-scraper-google-maps"

    @classmethod
    def normalize_record(cls, raw_row: Dict[str, Any], license_status: SourceLicenseStatus = SourceLicenseStatus.SYNTHETIC_FIXTURE) -> Lead:
        raw_json_str = json.dumps(raw_row, sort_keys=True)
        raw_hash = compute_sha256(raw_json_str)

        name = str(raw_row.get("title") or raw_row.get("name") or "Unknown Business").strip()
        category = str(raw_row.get("categoryName") or raw_row.get("category") or raw_row.get("business_type") or "General Contractor").strip()
        
        # Address parsing
        city = raw_row.get("city")
        state = raw_row.get("state")
        zip_code = raw_row.get("postalCode") or raw_row.get("zip")
        street = raw_row.get("address") or raw_row.get("street")
        
        address = AddressComponents(
            street=street,
            city=city,
            state=state,
            zip=zip_code,
            country=raw_row.get("country", "US")
        )

        phone = normalize_phone(raw_row.get("phone") or raw_row.get("phoneNumber"))
        emails = [e.strip() for e in raw_row.get("emails", []) if e and isinstance(e, str)]
        if raw_row.get("email") and isinstance(raw_row["email"], str):
            emails.append(raw_row["email"].strip())

        place_id = raw_row.get("placeId") or raw_row.get("googlePlaceId")

        source_ref = SourceReference(
            source_name="APIFY_NO_WEBSITE",
            actor_id=cls.ACTOR_ID,
            raw_id=raw_row.get("id") or place_id,
            observed_at=raw_row.get("last_updated") or raw_row.get("scrapedAt"),
            raw_hash=raw_hash
        )

        # Deterministic internal lead ID
        seed = f"{name}:{city or ''}:{state or ''}:{place_id or ''}"
        internal_id = "lead_" + compute_sha256(seed)[:16]

        is_ph = is_placeholder_lead(name, phone, emails)

        return Lead(
            internal_lead_id=internal_id,
            name=name,
            category=category,
            source_refs=[source_ref],
            address_components=address,
            phone=phone,
            emails=list(set(emails)),
            website_candidates=[],  # By definition, Source A indicates no website observed
            social_accounts=[],
            place_id=place_id,
            source_license_status=license_status,
            state=state,
            city=city,
            zip=zip_code,
            is_placeholder=is_ph
        )


class ApifyOldWebsiteAdapter:
    """Normalizer for Apify actor: xmiso_scrapers/old-websites-businesses-leads."""

    ACTOR_ID = "xmiso_scrapers/old-websites-businesses-leads"

    @classmethod
    def normalize_record(cls, raw_row: Dict[str, Any], license_status: SourceLicenseStatus = SourceLicenseStatus.SYNTHETIC_FIXTURE) -> Lead:
        raw_json_str = json.dumps(raw_row, sort_keys=True)
        raw_hash = compute_sha256(raw_json_str)

        name = str(raw_row.get("title") or raw_row.get("name") or "Unknown Business").strip()
        category = str(raw_row.get("categoryName") or raw_row.get("category") or raw_row.get("business_type") or "General Contractor").strip()
        
        city = raw_row.get("city")
        state = raw_row.get("state")
        zip_code = raw_row.get("postalCode") or raw_row.get("zip")
        street = raw_row.get("address") or raw_row.get("street")
        
        address = AddressComponents(
            street=street,
            city=city,
            state=state,
            zip=zip_code,
            country=raw_row.get("country", "US")
        )

        phone = normalize_phone(raw_row.get("phone") or raw_row.get("phoneNumber"))
        
        emails = []
        if isinstance(raw_row.get("emails"), list):
            emails.extend([e.strip() for e in raw_row["emails"] if isinstance(e, str)])
        elif isinstance(raw_row.get("email"), str):
            emails.append(raw_row["email"].strip())

        websites = []
        if raw_row.get("website"):
            websites.append(str(raw_row["website"]).strip())
        if raw_row.get("domain") and raw_row["domain"] not in websites:
            websites.append(str(raw_row["domain"]).strip())

        socials = []
        if isinstance(raw_row.get("social_links"), list):
            socials.extend(raw_row["social_links"])

        place_id = raw_row.get("googlePlaceId") or raw_row.get("placeId")

        source_ref = SourceReference(
            source_name="APIFY_OLD_WEBSITE",
            actor_id=cls.ACTOR_ID,
            raw_id=raw_row.get("id") or place_id,
            observed_at=raw_row.get("dataset_published_date") or raw_row.get("last_updated"),
            raw_hash=raw_hash
        )

        seed = f"{name}:{city or ''}:{state or ''}:{place_id or ''}"
        internal_id = "lead_" + compute_sha256(seed)[:16]
        is_ph = is_placeholder_lead(name, phone, emails)

        return Lead(
            internal_lead_id=internal_id,
            name=name,
            category=category,
            source_refs=[source_ref],
            address_components=address,
            phone=phone,
            emails=list(set(emails)),
            website_candidates=websites,
            social_accounts=socials,
            place_id=place_id,
            source_license_status=license_status,
            state=state,
            city=city,
            zip=zip_code,
            is_placeholder=is_ph
        )
