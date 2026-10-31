"""Export adapter for BZZY Field Operator.

Produces:
1. JSON export compatible with Field Operator resource models.
2. Flat CSV export for human review and offline field dispatch.
"""

import csv
import dataclasses
import json
import io
from typing import List, Dict, Any
from ..models import Lead, Assessment


def _to_serializable(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    if hasattr(obj, "value"):
        return obj.value
    return obj


def export_field_operator_json(records: List[Dict[str, Any]]) -> str:
    """Exports normalized leads and assessments to formatted JSON."""
    serialized_records = []
    for r in records:
        lead_dict = _to_serializable(r["lead"])
        assess_dict = _to_serializable(r["assessment"])
        serialized_records.append({
            "lead": lead_dict,
            "assessment": assess_dict
        })

    return json.dumps({
        "schema_version": "1.0.0",
        "system": "BZZY_LEAD_INTELLIGENCE",
        "record_count": len(serialized_records),
        "records": serialized_records
    }, indent=2, default=str)


def export_field_operator_csv(records: List[Dict[str, Any]]) -> str:
    """Exports records to CSV string with explicit quoting and provenance headers."""
    output = io.StringIO()
    fieldnames = [
        "lead_id",
        "name",
        "category",
        "city",
        "state",
        "zip",
        "phone",
        "emails",
        "operational_status",
        "outreach_readiness",
        "opportunity_score",
        "digital_gaps",
        "primary_source",
        "reason_codes"
    ]
    
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for r in records:
        lead: Lead = r["lead"]
        assess: Assessment = r["assessment"]
        
        primary_src = lead.source_refs[0].source_name if lead.source_refs else "UNKNOWN"
        
        writer.writerow({
            "lead_id": lead.internal_lead_id,
            "name": lead.name,
            "category": lead.category,
            "city": lead.city or "",
            "state": lead.state or "",
            "zip": lead.zip or "",
            "phone": lead.phone or "",
            "emails": ";".join(lead.emails),
            "operational_status": assess.business_status.value if hasattr(assess.business_status, "value") else str(assess.business_status),
            "outreach_readiness": assess.outreach_readiness.value if hasattr(assess.outreach_readiness, "value") else str(assess.outreach_readiness),
            "opportunity_score": f"{assess.opportunity_score:.1f}" if assess.opportunity_score is not None else "",
            "digital_gaps": ";".join([g.value if hasattr(g, "value") else str(g) for g in assess.digital_gaps]),
            "primary_source": primary_src,
            "reason_codes": ";".join(assess.reason_codes)
        })
        
    return output.getvalue()
