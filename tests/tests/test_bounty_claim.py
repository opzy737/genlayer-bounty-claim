"""
Reproducible validation for BountyClaim.

Requires the GenLayer testing suite:
    pip install genlayer-test

Run against a local GenVM simulator (starts automatically) with:
    gltest --network localnet tests/test_bounty_claim.py

Covers both settlement paths:
  - disputed: poster raises a dispute, resolution runs immediately
  - undisputed: no dispute is raised, resolution only succeeds once the
    response deadline has passed (tested with a zero-hour window so the
    deadline is already satisfied at submission time)
"""

from pathlib import Path
from gltest import get_contract_factory, create_account
from gltest.assertions import tx_execution_succeeded

CONTRACTS_DIR = Path(__file__).parent.parent


def deploy_contract(poster, submitter, response_deadline_hours):
    factory = get_contract_factory(
        contract_file_path=CONTRACTS_DIR / "bounty_claim.py"
    )
    return factory.deploy(
        account=poster,
        args=[
            poster.address,
            submitter.address,
            "Fix the null-pointer bug in the login handler and open a PR against main",
            1000,   # reward_amount
            response_deadline_hours,
        ],
    )


def test_disputed_settlement():
    poster = create_account()
    submitter = create_account()
    contract = deploy_contract(poster, submitter, response_deadline_hours=48)

    fund_tx = contract.fund_bounty(args=[], value=1000, account=poster).transact()
    assert tx_execution_succeeded(fund_tx)

    submit_tx = contract.submit_proof(
        args=["https://github.com/example/repo/pull/42",
              "Fixed and merged, see PR description for test coverage"],
        account=submitter,
    ).transact()
    assert tx_execution_succeeded(submit_tx)

    dispute_tx = contract.dispute_submission(
        args=["PR does not include a test for the fixed path",
              "https://github.com/example/repo/pull/42/files"],
        account=poster,
    ).transact()
    assert tx_execution_succeeded(dispute_tx)

    resolve_tx = contract.resolve_bounty(args=[], account=poster).transact()
    assert tx_execution_succeeded(resolve_tx)

    state = contract.get_state(args=[]).call()
    assert state["status"] == "resolved"
    assert state["verdict"] in ("approved", "rejected")
    assert state["deposited_amount"] == 0


def test_undisputed_settlement_after_deadline():
    poster = create_account()
    submitter = create_account()
    # Zero-hour window: the deadline is already satisfied the moment
    # proof is submitted, so resolution can proceed without a dispute
    # without the test needing to wait out a real window.
    contract = deploy_contract(poster, submitter, response_deadline_hours=0)

    fund_tx = contract.fund_bounty(args=[], value=1000, account=poster).transact()
    assert tx_execution_succeeded(fund_tx)

    submit_tx = contract.submit_proof(
        args=["https://github.com/example/repo/pull/43",
              "Fixed and merged, no objections expected"],
        account=submitter,
    ).transact()
    assert tx_execution_succeeded(submit_tx)

    resolve_tx = contract.resolve_bounty(args=[], account=poster).transact()
    assert tx_execution_succeeded(resolve_tx)

    state = contract.get_state(args=[]).call()
    assert state["status"] == "resolved"
    assert state["verdict"] in ("approved", "rejected")
    assert state["deposited_amount"] == 0
