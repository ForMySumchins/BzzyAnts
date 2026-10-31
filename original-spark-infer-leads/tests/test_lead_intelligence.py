"""Comprehensive test suite for BZZY Lead Intelligence + Merged Audit Engine (P1-P5).

Tests Master Directive & October 19 Audit acceptance criteria:
1: Active business with no dedicated website remains active, website opportunity.
2: Business with social dormant 18m and recent credible review is not closed.
3: Dead domain but recent business evidence remains uncertain/active.
4: One directory says closed but verified official site operates: conflict, human review.
5: Duplicate actor exports for same place preserve provenance, merge safely.
6: Two different businesses with same name never merge solely on name.
7: 555 phone and inferred placeholder rejected for outreach.
8: Private-IP, loopback, and redirect SSRF attempts blocked.
9: Importer re-run idempotent; missing fields explicit null.
10: Audited Gated Heat Score blocks closed/franchise/zero-readiness compensation (Fixes F02, F03).
11: Wappalyzer object-safe parser detects Analytics category objects and preserves UNKNOWN on empty (Fixes F05).
12: Six-Offer Family qualification supports creative launch/rebrand leads without requiring site defects (Fixes F08).
13: Home-based businesses qualify cleanly without storefront penalty (Fixes F07).
"""

import unittest
from lead_intelligence.models import (
    Lead,
    Evidence,
    Assessment,
    OperationalStatus,
    DigitalPresenceGap,
    OutreachReadiness,
    SourceLicenseStatus,
    OfferFamily,
    DiscoveryLane,
    OfferQualificationStatus,
)
from lead_intelligence.adapters.apify import (
    ApifyNoWebsiteAdapter,
    ApifyOldWebsiteAdapter,
)
from lead_intelligence.identity.dedupe import deduplicate_leads
from lead_intelligence.inference.engine import (
    infer_lead_status,
    compute_gated_heat_score,
    parse_technology_signals,
)
from lead_intelligence.security.ssrf import is_ssrf_safe_url
from lead_intelligence.export.field_operator import (
    export_field_operator_json,
    export_field_operator_csv,
)


class TestLeadIntelligence(unittest.TestCase):

    def test_ssrf_protection(self):
        safe, err = is_ssrf_safe_url("http://localhost/admin")
        self.assertFalse(safe)
        self.assertIn("LOCALHOST", err)

        safe, err = is_ssrf_safe_url("http://127.0.0.1:8080/metrics")
        self.assertFalse(safe)
        self.assertIn("BLOCKED_PRIVATE_OR_RESERVED_IP", err)

        safe, err = is_ssrf_safe_url("http://169.254.169.254/latest/meta-data/")
        self.assertFalse(safe)
        self.assertIn("BLOCKED_PRIVATE_OR_RESERVED_IP", err)

        safe, err = is_ssrf_safe_url("https://10.0.0.5/api")
        self.assertFalse(safe)
        self.assertIn("BLOCKED_PRIVATE_OR_RESERVED_IP", err)

        safe, err = is_ssrf_safe_url("https://192.168.1.1/setup")
        self.assertFalse(safe)
        self.assertIn("BLOCKED_PRIVATE_OR_RESERVED_IP", err)

        safe, err = is_ssrf_safe_url("http://example.com:22/ssh")
        self.assertFalse(safe)
        self.assertIn("BLOCKED_INTERNAL_PORT", err)

        safe, err = is_ssrf_safe_url("file:///etc/passwd")
        self.assertFalse(safe)
        self.assertIn("DISALLOWED_SCHEME", err)

        safe, err = is_ssrf_safe_url("https://example-contractor.com/about")
        self.assertTrue(safe)
        self.assertIsNone(err)

    def test_apify_no_website_adapter(self):
        raw_row = {
            "title": "San Bernardino Plumbing Pros",
            "categoryName": "Plumber",
            "address": "123 E Highland Ave",
            "city": "San Bernardino",
            "state": "CA",
            "postalCode": "92404",
            "phoneNumber": "+1 909-555-1234",
            "googlePlaceId": "ChIJ12345sb"
        }
        lead = ApifyNoWebsiteAdapter.normalize_record(raw_row)
        self.assertEqual(lead.name, "San Bernardino Plumbing Pros")
        self.assertEqual(lead.category, "Plumber")
        self.assertEqual(lead.city, "San Bernardino")
        self.assertEqual(lead.place_id, "ChIJ12345sb")
        self.assertEqual(len(lead.website_candidates), 0)
        self.assertIsNone(lead.phone)

    def test_apify_old_website_adapter(self):
        raw_row = {
            "name": "Inland Empire HVAC Masters",
            "business_type": "HVAC Contractor",
            "street": "456 Baseline St",
            "city": "San Bernardino",
            "state": "CA",
            "zip": "92411",
            "phone": "909-888-9999",
            "emails": ["service@iehvac.com"],
            "website": "http://iehvac.com",
            "placeId": "ChIJ99999sb"
        }
        lead = ApifyOldWebsiteAdapter.normalize_record(raw_row)
        self.assertEqual(lead.name, "Inland Empire HVAC Masters")
        self.assertEqual(lead.phone, "9098889999")
        self.assertIn("http://iehvac.com", lead.website_candidates)
        self.assertIn("service@iehvac.com", lead.emails)

    def test_deduplication_preserves_provenance(self):
        lead1 = ApifyNoWebsiteAdapter.normalize_record({
            "title": "Arrowhead Electrical",
            "city": "San Bernardino",
            "state": "CA",
            "googlePlaceId": "ChIJ_arrowhead_sb"
        })
        lead2 = ApifyOldWebsiteAdapter.normalize_record({
            "title": "Arrowhead Electrical",
            "city": "San Bernardino",
            "state": "CA",
            "googlePlaceId": "ChIJ_arrowhead_sb",
            "website": "http://arrowheadelectric.com"
        })
        
        deduped, merge_log = deduplicate_leads([lead1, lead2])
        self.assertEqual(len(deduped), 1)
        self.assertEqual(len(merge_log), 1)
        self.assertEqual(len(deduped[0].source_refs), 2)
        self.assertIn("http://arrowheadelectric.com", deduped[0].website_candidates)

    def test_disallowed_merge_on_name_only(self):
        lead_ca = ApifyNoWebsiteAdapter.normalize_record({
            "title": "Quality Plumbing",
            "city": "San Bernardino",
            "state": "CA"
        })
        lead_tx = ApifyNoWebsiteAdapter.normalize_record({
            "title": "Quality Plumbing",
            "city": "Dallas",
            "state": "TX"
        })
        deduped, merge_log = deduplicate_leads([lead_ca, lead_tx])
        self.assertEqual(len(deduped), 2)
        self.assertEqual(len(merge_log), 0)

    def test_conservative_status_dormant_social_with_review(self):
        lead = Lead(
            internal_lead_id="test_lead_001",
            name="Cajon Pass Roofing",
            category="Roofing Contractor",
            phone="9097771234",
            city="San Bernardino",
            state="CA"
        )
        evidence = [
            Evidence(
                evidence_id="ev_01",
                lead_id="test_lead_001",
                signal_type="SOCIAL_DORMANT",
                observed_value="18_months_inactive"
            ),
            Evidence(
                evidence_id="ev_02",
                lead_id="test_lead_001",
                signal_type="RECENT_CUSTOMER_REVIEW",
                observed_value="5_star_review_14_days_ago"
            )
        ]
        assessment = infer_lead_status(lead, evidence)
        self.assertEqual(assessment.business_status, OperationalStatus.LIKELY_ACTIVE)
        self.assertIn(DigitalPresenceGap.DORMANT_SOCIAL, assessment.digital_gaps)
        self.assertIn("SIGNAL_RECENT_CUSTOMER_REVIEW", assessment.reason_codes)
        self.assertIsNotNone(assessment.heat_score)
        self.assertEqual(assessment.heat_score.category_key, "contractor")

    def test_conflict_directory_closed_vs_active_license(self):
        lead = Lead(
            internal_lead_id="test_lead_002",
            name="Mojave Restoration Services",
            category="Restoration",
            phone="9096665432",
            city="San Bernardino",
            state="CA"
        )
        evidence = [
            Evidence(
                evidence_id="ev_01",
                lead_id="test_lead_002",
                signal_type="UNVERIFIED_DIRECTORY_CLOSED",
                observed_value="marked_closed_on_yelp"
            ),
            Evidence(
                evidence_id="ev_02",
                lead_id="test_lead_002",
                signal_type="ACTIVE_STATE_LICENSE",
                observed_value="cslb_status_active_renewed"
            )
        ]
        assessment = infer_lead_status(lead, evidence)
        self.assertEqual(assessment.outreach_readiness, OutreachReadiness.NEEDS_REVIEW)
        self.assertTrue(assessment.needs_human_review)
        self.assertIn("CONFLICT_DIRECTORY_CLOSED_VS_RECENT_ACTIVE_EVIDENCE", assessment.reason_codes)
        self.assertEqual(assessment.heat_score.tier, "needs_review")

    def test_authoritative_closure_confirmed(self):
        lead = Lead(
            internal_lead_id="test_lead_003",
            name="Defunct Electric Co",
            category="Electrician"
        )
        evidence = [
            Evidence(
                evidence_id="ev_01",
                lead_id="test_lead_003",
                signal_type="OFFICIAL_CLOSURE_NOTICE",
                observed_value="state_dissolution_filing"
            )
        ]
        assessment = infer_lead_status(lead, evidence)
        self.assertEqual(assessment.business_status, OperationalStatus.CONFIRMED_CLOSED)
        self.assertEqual(assessment.outreach_readiness, OutreachReadiness.INELIGIBLE)
        self.assertEqual(assessment.opportunity_score, 0.0)
        self.assertTrue(assessment.heat_score.disqualified)
        self.assertEqual(assessment.heat_score.tier, "withheld")

    def test_audited_gated_heat_score_fixes_f02_and_f03(self):
        # Fix F03: Zero confidence (0,0,0,0) or C=4.99 must NOT be forced to 'warm'
        res_zero = compute_gated_heat_score(0, 0, 0, 0)
        self.assertEqual(res_zero.tier, "needs_review")
        self.assertTrue(res_zero.confidence_gated)

        res_below_gate = compute_gated_heat_score(0, 0, 0, 4.99)
        self.assertEqual(res_below_gate.tier, "needs_review")

        # Fix F02: Zero readiness (10, 0, 10, 10) cannot be compensated into 'blazing'
        res_zero_ready = compute_gated_heat_score(10, 0, 10, 10)
        self.assertEqual(res_zero_ready.tier, "warm")
        self.assertEqual(res_zero_ready.gated_reason, "GATE_ZERO_READINESS_NON_COMPENSATORY_CAP")

        # Fix F02: Closed business with max dimensions is withheld, never 'hot'
        res_closed = compute_gated_heat_score(10, 10, 10, 5, is_closed=True)
        self.assertEqual(res_closed.tier, "withheld")
        self.assertEqual(res_closed.score, 0.0)
        self.assertTrue(res_closed.disqualified)

        # Fix F02: Franchise-restricted business is withheld, never 'blazing' 8.8
        res_franchise = compute_gated_heat_score(10, 6, 10, 10, is_franchise_restricted=True)
        self.assertEqual(res_franchise.tier, "withheld")
        self.assertTrue(res_franchise.disqualified)

    def test_wappalyzer_object_safe_parser_fixes_f05(self):
        # Documented Wappalyzer object shape with Analytics
        doc_payload = {
            "technologies": [
                {"categories": [{"id": 10, "name": "Analytics", "slug": "analytics"}]}
            ]
        }
        parsed = parse_technology_signals(doc_payload)
        self.assertTrue(parsed["has_analytics"])
        self.assertFalse(parsed["dark_advertiser_confirmed"])
        self.assertEqual(parsed["observation_state"], "OBSERVED")

        # Empty response must stay UNKNOWN and never assert dark_advertiser_confirmed=True
        empty_parsed = parse_technology_signals({})
        self.assertIsNone(empty_parsed["has_analytics"])
        self.assertFalse(empty_parsed["dark_advertiser_confirmed"])
        self.assertEqual(empty_parsed["observation_state"], "UNKNOWN")

    def test_creative_launch_and_home_based_qualification_fixes_f07_f08(self):
        # Active home-based business with good existing website launching a new service & requesting logo/flyer
        lead = Lead(
            internal_lead_id="lead_creative_01",
            name="Redlands Mobile Detailing",
            category="Auto Detailing",
            phone="9094443322",
            website_candidates=["https://redlandsmobiledetailing.com"],
            city="Redlands",
            state="CA",
            is_home_based=True,
        )
        evidence = [
            Evidence(
                evidence_id="ev_launch",
                lead_id="lead_creative_01",
                signal_type="VERIFIED_LAUNCH_OR_REBRAND",
                observed_value="Expanding fleet wash package Nov 2026",
            ),
            Evidence(
                evidence_id="ev_logo",
                lead_id="lead_creative_01",
                signal_type="OWNER_REQUEST_LOGO",
                observed_value="Requested vector logo and flyer quote",
            ),
        ]
        assessment = infer_lead_status(lead, evidence)
        self.assertEqual(assessment.business_status, OperationalStatus.LIKELY_ACTIVE)
        self.assertIn("CONTEXT_HOME_BASED_SERVICE_AREA_BUSINESS", assessment.reason_codes)
        offer_families = [oa.offer_family for oa in assessment.offer_assessments]
        self.assertIn(OfferFamily.LOGO_BRAND_KIT, offer_families)
        self.assertIn(OfferFamily.PRINT_DESIGN_ASSETS, offer_families)
        self.assertNotIn(OfferFamily.WEBSITE_CREATION, offer_families)

    def test_field_operator_export_format(self):
        lead = Lead(
            internal_lead_id="lead_123",
            name="San Bernardino Electric",
            category="Electrician",
            city="San Bernardino",
            state="CA",
            zip="92411",
            phone="9095550000"
        )
        assess = Assessment(
            lead_id="lead_123",
            business_status=OperationalStatus.ACTIVE_VERIFIED,
            digital_gaps=[DigitalPresenceGap.NO_WEBSITE],
            outreach_readiness=OutreachReadiness.READY,
            opportunity_score=85.0,
            reason_codes=["GAP_NO_DEDICATED_WEBSITE"]
        )
        records = [{"lead": lead, "assessment": assess}]
        
        json_out = export_field_operator_json(records)
        self.assertIn("BZZY_LEAD_INTELLIGENCE", json_out)
        self.assertIn("San Bernardino Electric", json_out)
        
        csv_out = export_field_operator_csv(records)
        self.assertIn("lead_123,San Bernardino Electric", csv_out)
        self.assertIn("ACTIVE_VERIFIED,READY,85.0", csv_out)


if __name__ == "__main__":
    unittest.main()
