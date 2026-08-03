"""Safety invariants for the owner-approved PR-only coding worker."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "codex-agent-task.yml"


class AgentSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_codex_job_has_no_repository_write_permission(self) -> None:
        generate = self.workflow.index("  generate_patch:")
        open_pr = self.workflow.index("  open_pr:")
        worker = self.workflow[generate:open_pr]
        self.assertIn("contents: read", worker)
        self.assertNotIn("contents: write", worker)
        self.assertIn("persist-credentials: false", worker)

    def test_worker_uses_workspace_sandbox_and_drops_sudo(self) -> None:
        self.assertIn("uses: openai/codex-action@v1", self.workflow)
        self.assertIn("sandbox: workspace-write", self.workflow)
        self.assertIn("safety-strategy: drop-sudo", self.workflow)
        self.assertIn("output-file: /tmp/codex-result.md", self.workflow)

    def test_only_separate_job_can_push_and_it_opens_pr(self) -> None:
        open_pr = self.workflow[self.workflow.index("  open_pr:") :]
        self.assertIn("contents: write", open_pr)
        self.assertIn("pull-requests: write", open_pr)
        self.assertIn('branch="codex/agent-task-$RUN_ID"', open_pr)
        self.assertIn("gh pr create", open_pr)
        self.assertIn("--base main", open_pr)

    def test_workflow_has_no_deploy_or_store_submission(self) -> None:
        lowered = self.workflow.lower()
        self.assertNotIn("eas submit", lowered)
        self.assertNotIn("eas build", lowered)
        self.assertNotIn("apple-actions", lowered)
        self.assertNotIn("google-play", lowered)


if __name__ == "__main__":
    unittest.main()
