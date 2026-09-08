import pytest

from security.harness import run_harness


@pytest.mark.asyncio
async def test_standard_security_harness_passes_without_external_model():
    report = await run_harness(workspace_id=1, project_id=2)
    assert report["status"] == "REVIEW"
    assert report["failedCases"] == 0
    assert report["passedCases"] == 8
    assert report["blockedCases"] == 1


@pytest.mark.asyncio
async def test_harness_can_run_selected_case_only():
    report = await run_harness(workspace_id=1, project_id=2, case_ids=["tenant-scope-boundary"])
    assert report["totalCases"] == 1
    assert report["results"][0]["status"] == "PASS"


@pytest.mark.asyncio
async def test_harness_rejects_unknown_cases():
    with pytest.raises(ValueError):
        await run_harness(workspace_id=1, project_id=2, case_ids=["not-a-real-case"])
