"""Legal-document versions. Bump on any material change to the corresponding
static HTML (privacy.html / terms.html). The client reads these via
GET /api/policy/versions to detect "policy changed since you consented" and the
consent record stamps the version the user agreed to."""

PRIVACY_VERSION = "2026-06-23"
TERMS_VERSION = "2026-06-23"
