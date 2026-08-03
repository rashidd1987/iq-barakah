"""Safety invariants for the Reports-bot production approval workflow."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "approve-report-bot-deploy.yml"


class ReportDeployApprovalSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_only_requests_telegram_approval(self) -> None:
        self.assertIn("wait_for_telegram_approval.py", self.workflow)
        self.assertIn("APPROVAL_API_URL", self.workflow)
        self.assertIn("APPROVAL_API_SECRET", self.workflow)
        self.assertIn("permissions:\n  contents: read", self.workflow)

    def test_approval_is_bound_to_exact_full_commit_sha(self) -> None:
        self.assertIn('^[0-9a-f]{40}$', self.workflow)
        self.assertIn(
            '--idempotency-key "reports-production:$APPROVED_COMMIT_SHA"',
            self.workflow,
        )
        self.assertIn("ref: ${{ inputs.commit_sha }}", self.workflow)

    def test_workflow_has_no_deployment_commands_or_write_permissions(self) -> None:
        lowered = self.workflow.lower()
        self.assertNotIn("git push", lowered)
        self.assertNotIn("ssh ", lowered)
        self.assertNotIn("scp ", lowered)
        self.assertNotIn("contents: write", lowered)
        self.assertNotIn("amvera", lowered)


if __name__ == "__main__":
    unittest.main()
