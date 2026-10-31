import os, json, hashlib
from typing import List, Dict, Any
from packages.contracts.models import SourceRecord, LicenseRightsTag

class BaseAdapter:
    def __init__(self, jurisdiction_id: str, adapter_type: str):
        self.jurisdiction_id = jurisdiction_id
        self.adapter_type = adapter_type
    def hash_payload(self, data: Any) -> str:
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode('utf-8')).hexdigest()

class SanBernardinoArcGISAdapter(BaseAdapter):
    def __init__(self):
        super().__init__("us-ca-sbcounty", "arcgis-parcels")
    def fetch_records(self) -> List[SourceRecord]:
        records = [
            {"apn": "0133-121-04-0000", "address": "385 N Arrowhead Ave", "city": "San Bernardino", "lat": 34.1083, "lng": -117.2898, "use": "Commercial"},
            {"apn": "0238-191-08-0000", "address": "8353 Sierra Ave", "city": "Fontana", "lat": 34.0922, "lng": -117.4350, "use": "Retail"}
        ]
        return [
            SourceRecord(source_id=f"arcgis-{r['apn']}", adapter_type=self.adapter_type, jurisdiction_id=self.jurisdiction_id, raw_sha256=self.hash_payload(r), raw_payload=r)
            for r in records
        ]

class ApifyScraperAdapter(BaseAdapter):
    def __init__(self, scraper_type: str):
        super().__init__("us-ca-sbcounty", f"apify-{scraper_type}")
    def normalize_leads(self, raw_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        clean = []
        for item in raw_items:
            phone = item.get("phone", "")
            if "555-" in phone or "5550" in phone or phone.startswith("555"):
                continue
            clean.append({
                "name": item.get("title") or item.get("name"),
                "phone": phone,
                "domain": item.get("website"),
                "city": item.get("city", "San Bernardino"),
                "address": item.get("address", ""),
                "place_id": item.get("placeId"),
                "digital_gap": "NO_WEBSITE" if not item.get("website") else "OUTDATED_WEBSITE"
            })
        return clean
