# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
import json
import typing
from datetime import datetime


class BountyClaim(gl.Contract):
    """
    Bounty / proof-of-work verification contract.

    A poster escrows a reward for a defined task (e.g. "fix issue #42",
    "produce a 500-word summary of X"). A submitter claims completion by
    citing a verifiable proof URL (a merged PR, a published deliverable,
    a commit, etc). The poster gets a response window to dispute the
    submission. The contract then fetches the cited proof directly and
    has validators reach consensus, via GenLayer's Equivalence Principle,
    on whether the fetched content actually satisfies the task spec —
    never on the submitter's description alone. The escrowed reward is
    paid to the submitter on a confirmed match, or refunded to the
    poster if rejected.
    """

    poster: str
    submitter: str
    task_spec: str
    reward_amount: u256
    deposited_amount: u256
    status: str  # "pending_funds" | "open" | "submitted" | "resolved" | "cancelled"

    proof_url: str
    proof_note: str
    poster_dispute: str
    poster_dispute_url: str

    response_deadline_hours: u256
    submitted_at: str  # ISO timestamp, set when proof is submitted

    verdict: str          # "approved" | "rejected" | ""
    verdict_reason: str

    def __init__(self, poster: str, submitter: str, task_spec: str,
                 reward_amount: u256, response_deadline_hours: u256 = u256(48)):
        self.poster = poster
        self.submitter = submitter
        self.task_spec = task_spec
        self.reward_amount = reward_amount
        self.deposited_amount = 0
        self.status = "pending_funds"

        self.proof_url = ""
        self.proof_note = ""
        self.poster_dispute = ""
        self.poster_dispute_url = ""

        self.response_deadline_hours = response_deadline_hours
        self.submitted_at = ""

        self.verdict = ""
        self.verdict_reason = ""

    @gl.public.write.payable
    def fund_bounty(self) -> None:
        assert self.status == "pending_funds", "Bounty is not accepting a deposit"
        assert str(gl.message.sender_address) == self.poster, "Only the poster can fund the bounty"
        assert gl.message.value >= self.reward_amount, "Deposit is less than the agreed reward"
        self.deposited_amount = gl.message.value
        self.status = "open"

    def _now_iso(self) -> str:
        def get_now() -> str:
            page = gl.get_webpage("https://worldtimeapi.org/api/timezone/Etc/UTC", mode="text")
            return json.loads(page)["utc_datetime"]

        return gl.eq_principle.strict_eq(get_now)

    @gl.public.write
    def submit_proof(self, proof_url: str, note: str = "") -> None:
        assert self.status == "open", "Bounty is not open for submissions"
        assert str(gl.message.sender_address) == self.submitter, "Only the assigned submitter can submit proof"
        assert proof_url, "A verifiable proof URL is required"

        self.proof_url = proof_url
        self.proof_note = note
        self.submitted_at = self._now_iso()
        self.status = "submitted"

    @gl.public.write
    def dispute_submission(self, reason: str, source_url: str = "") -> None:
        assert self.status == "submitted", "No pending submission to dispute"
        assert str(gl.message.sender_address) == self.poster, "Only the poster can dispute a submission"
        self.poster_dispute = reason
        self.poster_dispute_url = source_url

    @gl.public.write
    def resolve_bounty(self) -> typing.Any:
        assert self.status == "submitted", "No pending submission to resolve"

        has_dispute = bool(self.poster_dispute)

        if not has_dispute:
            submit_start = self.submitted_at
            window_hours = self.response_deadline_hours

            def check_deadline() -> str:
                page = gl.get_webpage("https://worldtimeapi.org/api/timezone/Etc/UTC", mode="text")
                now = datetime.fromisoformat(json.loads(page)["utc_datetime"].replace("Z", "+00:00"))
                start = datetime.fromisoformat(submit_start.replace("Z", "+00:00"))
                elapsed_hours = (now - start).total_seconds() / 3600
                return json.dumps({"deadline_passed": elapsed_hours >= window_hours})

            deadline_passed = json.loads(gl.eq_principle.strict_eq(check_deadline))["deadline_passed"]
            assert deadline_passed, (
                "The poster must dispute, or the response deadline must "
                "pass, before an undisputed submission auto-resolves"
            )

        task_spec = self.task_spec
        proof_url = self.proof_url
        proof_note = self.proof_note
        poster_dispute = self.poster_dispute or "(no dispute raised)"
        poster_dispute_url = self.poster_dispute_url

        def get_verdict() -> str:
            proof_content = "(no proof URL provided)"
            if proof_url:
                try:
                    proof_content = gl.get_webpage(proof_url, mode="text")[:3000]
                except Exception:
                    proof_content = "(proof URL could not be retrieved)"

            dispute_content = "(no dispute source provided)"
            if poster_dispute_url:
                try:
                    dispute_content = gl.get_webpage(poster_dispute_url, mode="text")[:3000]
                except Exception:
                    dispute_content = "(dispute source URL could not be retrieved)"

            prompt = f"""
You are an impartial reviewer judging whether submitted proof-of-work
satisfies a bounty's task specification. Base your decision only on
the task spec and the actual fetched content below — not on the
submitter's or poster's descriptions of what it shows.

TASK SPEC:
{task_spec}

SUBMITTER'S NOTE:
{proof_note}
FETCHED PROOF CONTENT (from the submitted URL):
{proof_content}

POSTER'S DISPUTE (if any):
{poster_dispute}
FETCHED DISPUTE SOURCE CONTENT (if any):
{dispute_content}

Decide whether the fetched proof content actually satisfies the task
spec. The "verdict" field MUST be exactly the string "approved" or
exactly the string "rejected" — no other value is valid. Respond ONLY
with compact JSON in this exact shape, no extra text:
{{"verdict": "approved" or "rejected", "reason": "one sentence explanation citing the specific proof content"}}
"""
            result = gl.exec_prompt(prompt)
            result = result.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(result)
            assert parsed.get("verdict") in ("approved", "rejected"), "Invalid verdict value from reviewer"
            return json.dumps(parsed, sort_keys=True)

        raw = gl.eq_principle.strict_eq(get_verdict)
        parsed = json.loads(raw)

        assert parsed["verdict"] in ("approved", "rejected"), "Resolution produced an invalid verdict"

        self.verdict = parsed["verdict"]
        self.verdict_reason = parsed["reason"]

        payout_amount = self.deposited_amount
        payout_to = self.submitter if self.verdict == "approved" else self.poster

        self.deposited_amount = 0
        self.status = "resolved"

        gl.evm.emit_transfer(Address(payout_to), payout_amount)

        return parsed

    @gl.public.write
    def cancel_before_submission(self) -> None:
        """Lets the poster reclaim the reward if nobody ever submits proof."""
        assert self.status == "open", "Can only cancel an open, unsubmitted bounty"
        assert str(gl.message.sender_address) == self.poster, "Only the poster can cancel"

        refund_amount = self.deposited_amount
        self.deposited_amount = 0
        self.status = "cancelled"

        gl.evm.emit_transfer(Address(self.poster), refund_amount)

    @gl.public.view
    def get_state(self) -> dict:
        return {
            "poster": self.poster,
            "submitter": self.submitter,
            "task_spec": self.task_spec,
            "reward_amount": self.reward_amount,
            "deposited_amount": self.deposited_amount,
            "status": self.status,
            "proof_url": self.proof_url,
            "proof_note": self.proof_note,
            "poster_dispute": self.poster_dispute,
            "poster_dispute_url": self.poster_dispute_url,
            "response_deadline_hours": self.response_deadline_hours,
            "submitted_at": self.submitted_at,
            "verdict": self.verdict,
            "verdict_reason": self.verdict_reason,
      }
