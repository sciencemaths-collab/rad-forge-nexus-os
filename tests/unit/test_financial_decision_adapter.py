import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest

from nexus_os.financial_decision_adapter import (
    FinancialDecisionAdapter,
    FinancialDecisionAdapterError,
    _digest,
)

QUALIFICATION = json.loads(
    (Path(__file__).parents[1] / "fixtures/financial-decision-qualification-0.2.0.json").read_text()
)


def payload():
    return {"prices": list(range(100, 180))}


def result(request):
    return {
        "schema_version": "1.0",
        "engine_id": "financial-algorithm",
        "engine_version": "0.2.0",
        "adapter_version": "1.0.0",
        "capability_id": "rad.decision.financial",
        "request_digest": _digest(request),
        "operation": "market.assess",
        "decision": {
            "recommendation": "REVIEW_MARKET_ASSESSMENT",
            "signal": "POSITIVE",
            "up_probability": 0.75,
            "horizon": 5,
            "window": 20,
        },
        "execution_authorized": False,
        "limitations": ["decision_support_only"],
    }


def adapter(call):
    return FinancialDecisionAdapter(call, QUALIFICATION)


def test_manifest_requires_approval_qualification_and_denies_network():
    manifest = adapter(result).manifest()
    assert manifest.capability_id == "rad.decision.financial"
    assert manifest.approval_required is True
    assert manifest.qualification_required is True
    assert manifest.network_access.value == "DENIED"
    assert "trade.execute" not in manifest.operations


def test_validated_non_executing_decision():
    output = asyncio.run(adapter(result).execute("market.assess", payload()))
    assert output["decision"]["signal"] == "POSITIVE"
    assert output["execution_authorized"] is False


@pytest.mark.parametrize("field", ["engine_version", "request_digest", "execution_authorized"])
def test_tampered_identity_digest_or_authority_is_rejected(field):
    def broken(request):
        output = deepcopy(result(request))
        output[field] = {
            "engine_version": "9.0.0",
            "request_digest": "sha256:" + "0" * 64,
            "execution_authorized": True,
        }[field]
        return output

    with pytest.raises(FinancialDecisionAdapterError):
        asyncio.run(adapter(broken).execute("market.assess", payload()))


def test_transaction_and_unbounded_requests_are_rejected():
    with pytest.raises(FinancialDecisionAdapterError, match="unsupported"):
        asyncio.run(adapter(result).execute("trade.execute", {}))
    with pytest.raises(FinancialDecisionAdapterError, match="bounded"):
        asyncio.run(
            adapter(result).execute(
                "valuation.estimate",
                {"cashflows": [100, 110], "discount_rate": 0.10, "simulations": 10_000_000},
            )
        )


def test_engine_errors_are_safely_wrapped():
    bound = adapter(lambda request: (_ for _ in ()).throw(RuntimeError("account-secret")))
    with pytest.raises(FinancialDecisionAdapterError, match="execution failed") as captured:
        asyncio.run(bound.execute("market.assess", payload()))
    assert "account-secret" not in str(captured.value)
