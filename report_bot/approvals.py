from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import secrets
from typing import Literal


ApprovalStatus = Literal["pending", "approved", "rejected", "expired"]


@dataclass(frozen=True)
class Approval:
    id: str
    idempotency_key: str
    project: str
    action: str
    description: str
    risk: str
    status: ApprovalStatus
    created_at: str
    expires_at: str
    decided_at: str | None = None
    decided_by: int | None = None


class ApprovalStore:
    def __init__(self, data_dir: str) -> None:
        self.path = Path(data_dir) / "approvals.json"
        self._items = self._load()

    def create(
        self,
        *,
        idempotency_key: str,
        project: str,
        action: str,
        description: str,
        risk: str,
        ttl_minutes: int = 60,
        now: datetime | None = None,
    ) -> tuple[Approval, bool]:
        existing = next(
            (
                item
                for item in self._items.values()
                if item.idempotency_key == idempotency_key
            ),
            None,
        )
        if existing:
            return self._with_expiry(existing, now), False

        current = now or datetime.now(timezone.utc)
        approval = Approval(
            id=secrets.token_urlsafe(12),
            idempotency_key=idempotency_key,
            project=project,
            action=action,
            description=description,
            risk=risk,
            status="pending",
            created_at=current.isoformat(),
            expires_at=(current + timedelta(minutes=ttl_minutes)).isoformat(),
        )
        self._items[approval.id] = approval
        self._save()
        return approval, True

    def get(self, approval_id: str, now: datetime | None = None) -> Approval | None:
        item = self._items.get(approval_id)
        return self._with_expiry(item, now) if item else None

    def decide(
        self,
        approval_id: str,
        *,
        approved: bool,
        owner_id: int,
        now: datetime | None = None,
    ) -> Approval | None:
        item = self.get(approval_id, now)
        if item is None or item.status != "pending":
            return item
        current = now or datetime.now(timezone.utc)
        decided = Approval(
            **{
                **asdict(item),
                "status": "approved" if approved else "rejected",
                "decided_at": current.isoformat(),
                "decided_by": owner_id,
            }
        )
        self._items[approval_id] = decided
        self._save()
        return decided

    def _with_expiry(
        self, item: Approval, now: datetime | None = None
    ) -> Approval:
        current = now or datetime.now(timezone.utc)
        if (
            item.status == "pending"
            and datetime.fromisoformat(item.expires_at) <= current
        ):
            item = Approval(**{**asdict(item), "status": "expired"})
            self._items[item.id] = item
            self._save()
        return item

    def _load(self) -> dict[str, Approval]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return {item["id"]: Approval(**item) for item in raw}
        except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
            return {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                [asdict(item) for item in self._items.values()],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.path)

