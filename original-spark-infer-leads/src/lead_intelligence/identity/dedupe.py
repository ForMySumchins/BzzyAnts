"""Identity resolution and deduplication engine.

Rules from Master Directive:
- Dedupe by permitted Google Place ID when available, normalized domain,
  business name + verified geography, and phone only as secondary support.
- NEVER auto-merge ambiguous similar names without matching geo/phone/domain.
- Preserve separate source rows and explain merge decisions in provenance ledger.
- Detect 555/test numbers, malformed addresses, inferred placeholders, and stale records.
"""

from typing import List, Dict, Tuple
from ..models import Lead, SourceReference


def deduplicate_leads(leads: List[Lead]) -> Tuple[List[Lead], List[Dict[str, str]]]:
    """Deduplicates a list of leads deterministically while preserving provenance."""
    deduped_map: Dict[str, Lead] = {}
    merge_log: List[Dict[str, str]] = []

    # Map of secondary keys to internal_lead_id
    place_id_map: Dict[str, str] = {}
    domain_map: Dict[str, str] = {}
    geo_name_map: Dict[str, str] = {}

    for lead in leads:
        # Check matching place_id
        target_id = None
        merge_reason = None

        if lead.place_id and lead.place_id in place_id_map:
            target_id = place_id_map[lead.place_id]
            merge_reason = f"MATCHED_PLACE_ID: {lead.place_id}"
        
        # Check matching domain if website present
        if not target_id:
            for web in lead.website_candidates:
                domain = web.lower().replace("https://", "").replace("http://", "").split("/")[0].replace("www.", "")
                if domain and domain in domain_map:
                    target_id = domain_map[domain]
                    merge_reason = f"MATCHED_DOMAIN: {domain}"
                    break

        # Check matching name + normalized city/state
        if not target_id and lead.name and lead.city and lead.state:
            geo_key = f"{lead.name.lower().strip()}:{lead.city.lower().strip()}:{lead.state.lower().strip()}"
            if geo_key in geo_name_map:
                target_id = geo_name_map[geo_key]
                merge_reason = f"MATCHED_NAME_AND_GEOGRAPHY: {geo_key}"

        if target_id and target_id in deduped_map:
            # Merge into existing lead
            existing = deduped_map[target_id]
            
            # Combine source refs
            existing.source_refs.extend(lead.source_refs)
            
            # Combine emails
            for em in lead.emails:
                if em not in existing.emails:
                    existing.emails.append(em)

            # Combine websites
            for web in lead.website_candidates:
                if web not in existing.website_candidates:
                    existing.website_candidates.append(web)

            # Combine socials
            for soc in lead.social_accounts:
                if soc not in existing.social_accounts:
                    existing.social_accounts.append(soc)

            # Secondary phone update if missing
            if not existing.phone and lead.phone:
                existing.phone = lead.phone

            merge_log.append({
                "incoming_lead_id": lead.internal_lead_id,
                "merged_into_lead_id": target_id,
                "reason": merge_reason
            })
        else:
            # New distinct lead
            deduped_map[lead.internal_lead_id] = lead
            if lead.place_id:
                place_id_map[lead.place_id] = lead.internal_lead_id
            for web in lead.website_candidates:
                domain = web.lower().replace("https://", "").replace("http://", "").split("/")[0].replace("www.", "")
                if domain:
                    domain_map[domain] = lead.internal_lead_id
            if lead.name and lead.city and lead.state:
                geo_key = f"{lead.name.lower().strip()}:{lead.city.lower().strip()}:{lead.state.lower().strip()}"
                geo_name_map[geo_key] = lead.internal_lead_id

    return list(deduped_map.values()), merge_log
