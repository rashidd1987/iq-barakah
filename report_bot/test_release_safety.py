"""Regression checks for the production PWA approval architecture."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release-pwa.yml"


class ReleaseSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_production_approval_is_requested_before_deploy(self) -> None:
        request_job = self.workflow.index("  request-approval:")
        deploy_job = self.workflow.index("  deploy:")
        self.assertLess(request_job, deploy_job)
        self.assertIn("needs: [build, request-approval]", self.workflow)
        self.assertIn("environment: ${{ inputs.target }}", self.workflow)

    def test_github_and_telegram_share_one_approval(self) -> None:
        self.assertIn("--github-run-id \"${GITHUB_RUN_ID}\"", self.workflow)
        self.assertIn("--create-only", self.workflow)
        self.assertIn(
            "--approval-id \"${{ needs.request-approval.outputs.approval_id }}\"",
            self.workflow,
        )

    def test_sync_happens_before_any_production_upload(self) -> None:
        checkout = self.workflow.index("- name: Checkout deployment scripts")
        synchronize = self.workflow.index(
            "- name: Synchronize GitHub approval with Telegram"
        )
        upload = self.workflow.index("- name: Upload PWA")
        self.assertLess(checkout, synchronize)
        self.assertLess(synchronize, upload)

    def test_production_confirmation_remains_required(self) -> None:
        self.assertGreaterEqual(
            self.workflow.count("confirm_production != 'RELEASE'"),
            2,
        )
        self.assertIn(
            'group: pwa-${{ inputs.target }}',
            self.workflow,
        )
        self.assertIn("cancel-in-progress: false", self.workflow)


if __name__ == "__main__":
    unittest.main()
