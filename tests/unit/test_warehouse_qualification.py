from nexus_os.warehouse_qualification import qualify


def test_formal_warehouse_qualification_passes_all_cases_deterministically():
    first = qualify()
    second = qualify()
    assert first == second
    assert first["qualification"] == "QUALIFIED_FOR_BOUNDED_INTEGER_INVENTORY_ALLOCATION"
    assert first["passed_count"] == first["case_count"] == 15
    assert all(case["deterministic_replay"] and case["verified"] for case in first["cases"])
    assert all(case["external_write_authorized"] is False for case in first["cases"])
