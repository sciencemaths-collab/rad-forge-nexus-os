from copy import deepcopy

import pytest

from nexus_os.financial_decision_adapter import (
    FinancialDecisionAdapterError,
    _digest,
    attest_financial_qualification,
)
from tests.unit.test_financial_decision_adapter import QUALIFICATION


def test_tampered_financial_qualification_is_rejected():
    tampered = deepcopy(QUALIFICATION)
    tampered["cases"][0]["execution_authorized"] = True
    with pytest.raises(FinancialDecisionAdapterError, match="not trusted"):
        attest_financial_qualification(tampered)


def test_self_signed_unqualified_financial_report_is_rejected():
    unqualified = deepcopy(QUALIFICATION)
    unqualified["qualification"] = "UNQUALIFIED"
    unqualified["report_digest"] = _digest(
        {key: value for key, value in unqualified.items() if key != "report_digest"}
    )
    with pytest.raises(FinancialDecisionAdapterError, match="not trusted"):
        attest_financial_qualification(unqualified)
