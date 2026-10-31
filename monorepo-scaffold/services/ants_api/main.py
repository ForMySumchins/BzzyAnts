from fastapi import FastAPI, HTTPException, Header, Query
from typing import Optional, List, Dict, Any
from datetime import datetime
from packages.contracts.models import Opportunity, Signal, FieldObservation, PackageSuggestion

app = FastAPI(title="BZZY Ants API", version="1.0.0")

DB_OPPORTUNITIES = {
    "opp-sb-01": Opportunity(
        opportunity_id="opp-sb-01", business_id="biz-ie-climate", site_id="site-sb-arrowhead",
        composite_score=88.5, score_breakdown={"no_website": 45.0, "active_permits": 25.0},
        active_signals=[Signal(signal_id="sig-01", signal_type="NO_WEBSITE_DETECTED", source_record_id="src-1", confidence=0.95)],
        status="OPEN_SCOUTED"
    )
}
DB_OBSERVATIONS = []

@app.get("/api/v1/opportunities")
def get_opportunities(min_score: float = 0.0):
    return {"kpi_summary": {"total": len(DB_OPPORTUNITIES)}, "opportunities": list(DB_OPPORTUNITIES.values())}

@app.get("/api/v1/geo/h3-cells")
def get_h3_cells():
    return {"type": "FeatureCollection", "features": []}

@app.get("/api/v1/opportunities/{opp_id}")
def get_detail(opp_id: str):
    if opp_id not in DB_OPPORTUNITIES: raise HTTPException(404, "Not found")
    return DB_OPPORTUNITIES[opp_id]

@app.post("/api/v1/opportunities/{opp_id}/package-suggestions")
def suggest_pkg(opp_id: str):
    return {"status": "CANDIDATE_PROPOSAL", "package_id": "pkg-web-starter"}

@app.post("/api/v1/observations/sync")
def sync_obs(obs: FieldObservation):
    DB_OBSERVATIONS.append(obs)
    return {"status": "SUCCESS", "observation_id": obs.observation_id}

@app.post("/api/v1/mantis-eye/extract")
def extract_ocr(payload: Dict[str, Any]):
    return {"status": "EXTRACTED_QUARANTINED", "fields": {"equipment": "HVAC Condenser"}}

@app.post("/api/v1/handoff/bees-export")
def export_bees(opp_id: str):
    return {"status": "CANDIDATE_PACKET_EXPORTED", "opportunity_id": opp_id}
