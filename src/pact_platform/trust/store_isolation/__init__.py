# Copyright 2026 Terrene Foundation
# Licensed under the Apache License, Version 2.0
"""Store isolation — management/data plane separation.

M17-1704: Logical plane isolation with separate store interfaces.

The management plane handles trust lifecycle operations:
- Genesis records, delegation records, constraint envelopes, attestations, revocations.

The data plane handles operational data:
- Audit anchors, posture changes.

Both planes share a single underlying store but enforce write restrictions:
- Data plane CANNOT write to management tables.
- Management plane CANNOT write to data plane tables.
- Both planes CAN read from the other plane's tables (for verification/oversight).
"""

from pact_platform.trust.store_isolation.data import DataPlaneStore
from pact_platform.trust.store_isolation.management import ManagementPlaneStore
from pact_platform.trust.store_isolation.violations import PlaneViolationError

__all__ = [
    "DataPlaneStore",
    "ManagementPlaneStore",
    "PlaneViolationError",
]
