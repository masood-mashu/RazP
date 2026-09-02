import os
import sys
sys.path.insert(0, os.path.abspath("."))
from dotenv import load_dotenv
load_dotenv()

from core.gemini_reasoner import GeminiReasoner
from core.schemas import TransactionTelemetry, PaymentMethod, CustomerMessage
from datetime import datetime

telem = TransactionTelemetry(
    payment_id='pay_smoke_001',
    invoice_id='inv_smoke_001',
    amount_inr=3200.0,
    gateway_error_code='GATEWAY_TIMEOUT',
    bank_raw_response_code='U30',
    payment_method=PaymentMethod.UPI_AUTOPAY,
    latency_ms=12400,
    bank_switch_degradation_score=0.85,
    attempt_count=1,
    last_inbound_message=CustomerMessage(
        message_text='bhai mere account se 3200 kat gaye par order confirm nahi hua, please help dobara mat katna'
    )
)

print("Starting smoke test...", flush=True)
model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
reasoner = GeminiReasoner(model=model_name)
result = reasoner.reason(telem, reference_time=datetime(2026, 9, 1, 14, 0, 0))

print('key_loaded:', bool(reasoner.api_key), flush=True)
print('model:', result.get('model'), flush=True)
print('is_live_gemini:', result.get('is_live_gemini'), flush=True)
print('fallback_used:', result.get('fallback_used'), flush=True)
print('latency_ms:', result.get('latency_ms'), flush=True)
print('redacted_error:', result.get('error'), flush=True)
if result.get('is_live_gemini'):
    out = result.get('reasoner_output')
    print('proposed_action:', out.proposed_action.value if out else None, flush=True)
    print('root_cause:', out.root_cause.value if out else None, flush=True)
    print('customer_intent:', out.customer_intent.value if out else None, flush=True)
