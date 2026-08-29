"""
Reproducible validation for BountyClaim.

Requires the GenLayer testing suite:
    pip install genlayer-test

Run against a local GenVM simulator (starts automatically) with:
    gltest --network localnet tests/test_bounty_claim.py
"""

from pathlib import Path
from gltest import get_contract_factory
from gltest.assertions import tx_execution_succeeded

CONTRACTS_DIR = Path(__file__).parent.parent / "contracts"


def deploy_contract():
    factory = get_contract_factory(
        contract_file_path=CONTRACTS_DIR / "bounty_claim.py"
    )
    return factory.deploy(
        args=[
            "0xPosterAddressPlaceholder00000000000001",
            "0xSubmitterAddressPlaceholder000000000001",
            "Fix the null-pointer bug in the login handler and open a PR against main",
            1000,   # reward_amount
            48,     # response_deadline_hours
        ]
    )


def test_full_bounty_lifecycle_loads_under_sdk():
    contract = deploy_contract()

    state = contract.get_state(args=[]).call()
    assert state["status"] == "pending_funds"
    assert state["reward_amount"] == 1000

    fund_tx = contract.fund_bounty(args=[], value=1000).transact()
    assert tx_execution_succeeded(fund_tx)

    state = contract.get_state(args=[]).call()
    assert state["status"] == "open"
    assert state["deposited_amount"] == 1000

    submit_tx = contract.submit_proof(
        args=["https://github.com/example/repo/pull/42",
              "Fixed and merged, see PR description for test coverage"]
    ).transact()
    assert tx_execution_succeeded(submit_tx)

    state = contract.get_state(args=[]).call()
    assert state["status"] == "submitted"

    dispute_tx = contract.dispute_submission(
        args=["PR does not include a test for the fixed path",
              "https://github.com/example/repo/pull/42/files"]
    ).transact()
    assert tx_execution_succeeded(dispute_tx)

    resolve_tx = contract.resolve_bounty(args=[]).transact()
    assert tx_execution_succeeded(resolve_tx)

    state = contract.get_state(args=[]).call()
    assert state["status"] == "resolved"
    assert state["verdict"] in ("approved", "rejected")
    assert state["deposited_amount"] == 0
