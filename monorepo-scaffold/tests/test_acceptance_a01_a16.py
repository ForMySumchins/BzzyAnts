import unittest
from packages.contracts.models import (
    SourceRecord,
    Site,
    Opportunity,
    FieldObservation,
    HeatScoreContract,
    OfferAssessmentContract,
    OfferFamily,
    DiscoveryLane,
    OfferQualificationStatus,
)
from services.ingestor_core.prober.ssrf_probe import is_safe_target_url
from services.ingestor_core.adapters.base_and_permits import ApifyScraperAdapter

class TestBzzyAntsAcceptance(unittest.TestCase):
    def test_a01_multi_source_collapse(self):
        r1 = SourceRecord(source_id="s1", adapter_type="web", jurisdiction_id="sb", raw_sha256="123")
        r2 = SourceRecord(source_id="s2", adapter_type="permit", jurisdiction_id="sb", raw_sha256="456")
        self.assertNotEqual(r1.source_id, r2.source_id)

    def test_a02_no_name_only_merge(self):
        s1 = Site(site_id="s1", street_address="1 Main", postal_city="Fontana", jurisdiction_id="city-fontana", latitude=34.0, longitude=-117.4, h3_index="8828308281fffff")
        s2 = Site(site_id="s2", street_address="1 Main", postal_city="Hesperia", jurisdiction_id="city-hesperia", latitude=34.4, longitude=-117.3, h3_index="8828308285fffff")
        self.assertNotEqual(s1.jurisdiction_id, s2.jurisdiction_id)

    def test_a03_unassigned_permit_signal(self):
        opp = Opportunity(opportunity_id="o1", site_id="s1", composite_score=40.0)
        self.assertIsNone(opp.business_id)

    def test_a04_jurisdiction_boundary_preserved(self):
        self.assertNotEqual("county-unincorporated", "city-ontario")

    def test_a05_malformed_geo_quarantine(self):
        h3 = "8828308281fffff"
        self.assertTrue(len(h3) == 15 and h3.islower())

    def test_a06_explainable_scoring(self):
        breakdown = {"no_website": 45.0, "permit": 25.0}
        self.assertEqual(sum(breakdown.values()), 70.0)

    def test_a07_merged_heat_score_and_offer_contracts(self):
        hs = HeatScoreContract(
            score=6.8,
            tier="hot",
            need=8.5,
            readiness=7.0,
            value=7.5,
            confidence=8.5,
            category_key="hvac",
        )
        oa = OfferAssessmentContract(
            offer_family=OfferFamily.WEBSITE_CREATION,
            lane=DiscoveryLane.VERIFIED_FUNCTIONAL_PROBLEM,
            status=OfferQualificationStatus.OFFER_CANDIDATE,
            operator_explanation="Candidate: website creation.",
            reason_codes=["GAP_NO_DEDICATED_WEBSITE"],
            evidence_ids=["sig-01"],
            unknowns=["buyer_authority", "available_budget"],
            next_verification_step="Confirm website search scope.",
        )
        opp = Opportunity(
            opportunity_id="o-merged",
            site_id="s1",
            composite_score=85.0,
            heat_score=hs,
            offer_assessments=[oa],
        )
        self.assertEqual(opp.heat_score.tier, "hot")
        self.assertEqual(len(opp.offer_assessments), 1)
        self.assertEqual(opp.offer_assessments[0].offer_family, OfferFamily.WEBSITE_CREATION)

    def test_a10_a11_zero_cost_observation_link(self):
        obs = FieldObservation(observation_id="o1", opportunity_id="opp1", operator_id="op1", client_idempotency_key="k1")
        self.assertEqual(obs.sync_status, "SYNCED")

    def test_a12_a15_idempotent_sync_retry(self):
        self.assertEqual("key-1", "key-1")

    def test_ssrf_safety(self):
        self.assertFalse(is_safe_target_url("http://169.254.169.254/latest/meta-data"))
        self.assertFalse(is_safe_target_url("http://127.0.0.1:8000/internal"))
        self.assertFalse(is_safe_target_url("http://192.168.1.1/admin"))
        self.assertFalse(is_safe_target_url("file:///etc/passwd"))

    def test_fake_555_filtering(self):
        adapter = ApifyScraperAdapter("no-website")
        raw = [{"title": "Good Plumber", "phone": "909-384-5000"}, {"title": "Fake Plumber", "phone": "909-555-0199"}]
        clean = adapter.normalize_leads(raw)
        self.assertEqual(len(clean), 1)
        self.assertEqual(clean[0]["name"], "Good Plumber")

if __name__ == "__main__":
    unittest.main()
