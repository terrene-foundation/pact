# Nexus K8s Probes + OpenAPI + Security Middleware

## K8s Probe Endpoints

```python
from nexus import Nexus, ProbeManager, ProbeState

app = Nexus([workflow])

# Probes auto-registered at:
# GET /healthz  — liveness (always 200 if process alive)
# GET /readyz   — readiness (200 when all workflows ready)
# GET /startup  — startup (200 after init complete)

# Manual state control
app.probe_manager.set_state(ProbeState.DRAINING)  # graceful shutdown
```

### ProbeState Transitions

`STARTING -> READY -> DRAINING -> FAILED` (thread-safe, atomic)

### Readiness Callbacks

```python
probe_mgr = ProbeManager()
probe_mgr.register_readiness_check("db", lambda: db.is_connected())
```

## OpenAPI Generation

```python
from nexus import OpenApiGenerator, OpenApiInfo

gen = OpenApiGenerator(info=OpenApiInfo(title="My API", version="1.0.0"))
gen.add_handler("/process", handler_fn)  # auto-derives schema from type hints
spec = gen.generate()  # OpenAPI 3.0.3 dict

# Auto-endpoint: GET /openapi.json
```

## Security Headers Middleware

```python
from nexus.middleware.security_headers import SecurityHeadersMiddleware, SecurityHeadersConfig

config = SecurityHeadersConfig(
    csp="default-src 'self'",
    hsts_max_age=31536000,
    x_frame_options="DENY",
)
# Applies: CSP, HSTS, X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy
```

## CSRF Middleware

```python
from nexus.middleware.csrf import CSRFMiddleware

csrf = CSRFMiddleware(
    allowed_origins=["https://app.example.com"],
    exempt_paths=["/api/webhooks"],
)
# Validates Origin/Referer on POST/PUT/DELETE/PATCH. GET/HEAD/OPTIONS bypass.
```

## Middleware Presets

```python
from nexus import Nexus
from nexus.presets import Preset

app = Nexus([workflow], preset=Preset.STANDARD)
# None: no middleware
# Lightweight: security headers
# Standard: + CSRF + CORS + rate limiting
# SaaS: + tenant isolation
# Enterprise: + audit logging
```

## Source Files

- `packages/kailash-nexus/src/nexus/probes.py`
- `packages/kailash-nexus/src/nexus/openapi.py`
- `packages/kailash-nexus/src/nexus/middleware/security_headers.py`
- `packages/kailash-nexus/src/nexus/middleware/csrf.py`
- `packages/kailash-nexus/src/nexus/presets.py`
