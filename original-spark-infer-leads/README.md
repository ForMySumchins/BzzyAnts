# BZZY Lead Intelligence (`infer-leads`)

Bounded offline lead intelligence and verification core for **BZZY Solutions** (NOT BzzyBees).

## Architectural Boundaries & Principles
- **Offline First**: Zero paid API calls, zero web scraping, zero automated outreach.
- **SSRF Hardening**: Outbound verification strictly blocks private IPs (RFC1918), loopback, link-local, IPv6 local, internal ports, and non-HTTP schemes.
- **Conservative Inference**: Businesses are never marked `CONFIRMED_CLOSED` without official authoritative documentation. Stale marketing is not business death.
- **Field Operator Interoperability**: Exports normalized JSON and CSV payloads adhering to the Field Operator resource model.

## Running Tests
```bash
PYTHONPATH=src python3 -m unittest discover tests
```
All 9 unit tests run offline in <0.01s with zero network dependencies.
