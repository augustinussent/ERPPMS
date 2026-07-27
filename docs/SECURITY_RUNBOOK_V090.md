# Security Runbook v0.9.0

- Terminate TLS at the reverse proxy and enable HSTS after validating every hostname.
- Configure Content-Security-Policy, X-Content-Type-Options, Referrer-Policy, frame-ancestors, upload-size limits, and rate limits at Nginx/Traefik.
- Keep ERPNext API keys in a secret manager; rotate quarterly and immediately after staff/vendor access changes.
- Use a separate HMAC secret for every webhook subscription. Private, loopback, link-local, and reserved webhook destinations are rejected.
- Review Hotel User Property Access monthly. System Manager is the only role allowed to run onboarding.
- Run dependency, container, and image scans in the deployment pipeline.
- Run a restore drill on an isolated site; checksum verification alone is not a restore test.
