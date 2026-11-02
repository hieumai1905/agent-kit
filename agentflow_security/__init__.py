"""Wave Đ2 prototypes: cryptographic receipt verification and conservative checks.

WARNING: No production trusted-host integration or OS-enforced write boundary.
No function in this package grants permission to mutate a product repository.
"""
from .approvals import (ApprovalChallengeLedger, ApprovalReceiptVerifier,
                        ReceiptError, CRYPTO_AVAILABLE)
from .gates import (CapabilityAssessment, GateDecision, assess_write_request,
                    adapter_capability_matrix, classify_tool_effect)

__all__ = [
    'ApprovalChallengeLedger', 'ApprovalReceiptVerifier', 'ReceiptError',
    'CRYPTO_AVAILABLE', 'CapabilityAssessment', 'GateDecision',
    'assess_write_request', 'adapter_capability_matrix', 'classify_tool_effect',
]
