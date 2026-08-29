# Bounty Claim — GenLayer Intelligent Contract

An Intelligent Contract for verified bounty payouts using GenLayer's Equivalence Principle for AI-arbitrated consensus, anchored to real proof sources.

## How it works

1. Poster escrows a reward via `fund_bounty()`.
2. Submitter submits proof via `submit_proof()`, citing a verifiable URL.
3. Poster gets a response window (default 48h) to dispute via `dispute_submission()`.
4. `resolve_bounty()` requires a dispute or a passed deadline. Validators fetch the actual proof (and dispute source, if any) and rule on whether it satisfies the task spec.
5. The escrowed reward auto-releases to whichever party the evidence supports.

## Methods

- `fund_bounty()` — payable, poster only
- `submit_proof(proof_url, note)` — submitter only
- `dispute_submission(reason, source_url)` — poster only
- `resolve_bounty()` — verified arbitration + automatic payout
- `cancel_before_submission()` — poster refund if unclaimed
- `get_state()` — full contract state

## Running tests

pip install genlayer-test
gltest --network localnet tests/test_bounty_claim.py

## Built for

GenLayer testnet — Intelligent Contracts builder category.
