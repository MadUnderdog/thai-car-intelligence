"""
Durable queue for document processing.

State machine: PENDING → IN_PROGRESS → SUCCEEDED/FAILED_RETRYABLE/FAILED_PERMANENT/NEEDS_REVIEW
Checkpoint/resume with deterministic keys.
"""
import json
import os
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Set
from datetime import datetime, timezone


class JobState(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_PERMANENT = "FAILED_PERMANENT"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass
class Job:
    """A single document processing job."""
    job_key: str  # deterministic: source_domain + url_or_hash
    url: str
    source_domain: str
    state: JobState = JobState.PENDING
    attempts: int = 0
    max_attempts: int = 3
    last_error: str = ""
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    result: Dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["state"] = self.state.value
        return d


class DurableQueue:
    """
    Durable document processing queue with checkpoint/resume.
    """

    def __init__(self, checkpoint_path: str):
        self.checkpoint_path = checkpoint_path
        self.jobs: Dict[str, Job] = {}
        self._load()

    def _load(self):
        """Load queue state from checkpoint file.
        FIX: Corrupted checkpoint fails loudly instead of silently resetting.
        """
        if os.path.exists(self.checkpoint_path):
            try:
                with open(self.checkpoint_path) as f:
                    data = json.load(f)
                for job_data in data.get("jobs", []):
                    job_data["state"] = JobState(job_data["state"])
                    job = Job(**job_data)
                    self.jobs[job.job_key] = job
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                # Corrupted checkpoint — fail loudly
                raise RuntimeError(
                    f"Corrupted queue checkpoint at {self.checkpoint_path}: {e}. "
                    f"Use --reset to start fresh or fix the checkpoint manually."
                )

    def save(self):
        """Persist queue state."""
        os.makedirs(os.path.dirname(self.checkpoint_path), exist_ok=True)
        data = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "jobs": [j.to_dict() for j in self.jobs.values()],
        }
        with open(self.checkpoint_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def enqueue(self, job_key: str, url: str, source_domain: str) -> Job:
        """Add a job to the queue. Returns existing job if already present."""
        if job_key in self.jobs:
            return self.jobs[job_key]
        job = Job(job_key=job_key, url=url, source_domain=source_domain)
        self.jobs[job_key] = job
        return job

    def claim_next(self, source_domain: Optional[str] = None) -> Optional[Job]:
        """Claim the next pending job. Returns None if no jobs available."""
        for job in self.jobs.values():
            if job.state != JobState.PENDING:
                continue
            if source_domain and job.source_domain != source_domain:
                continue
            if job.attempts >= job.max_attempts:
                job.state = JobState.FAILED_PERMANENT
                continue
            job.state = JobState.IN_PROGRESS
            job.started_at = datetime.now(timezone.utc).isoformat()
            job.attempts += 1
            return job
        return None

    def complete(self, job_key: str, result: Optional[Dict] = None):
        """Mark a job as succeeded."""
        if job_key in self.jobs:
            self.jobs[job_key].state = JobState.SUCCEEDED
            self.jobs[job_key].completed_at = datetime.now(timezone.utc).isoformat()
            if result:
                self.jobs[job_key].result = result

    def fail(self, job_key: str, error: str, retryable: bool = True):
        """Mark a job as failed."""
        if job_key in self.jobs:
            job = self.jobs[job_key]
            job.last_error = error[:500]
            if retryable and job.attempts < job.max_attempts:
                job.state = JobState.PENDING  # Will be retried
            else:
                job.state = JobState.FAILED_PERMANENT
            job.completed_at = datetime.now(timezone.utc).isoformat()

    def flag_review(self, job_key: str, reason: str = ""):
        """Flag a job for human review."""
        if job_key in self.jobs:
            self.jobs[job_key].state = JobState.NEEDS_REVIEW
            self.jobs[job_key].last_error = reason[:500]

    def stats(self) -> Dict[str, int]:
        """Return queue statistics."""
        counts = {}
        for job in self.jobs.values():
            counts[job.state.value] = counts.get(job.state.value, 0) + 1
        return counts

    def pending_count(self, source_domain: Optional[str] = None) -> int:
        """Count pending jobs."""
        return len([j for j in self.jobs.values()
                    if j.state == JobState.PENDING
                    and (not source_domain or j.source_domain == source_domain)])

    def completed_keys(self) -> Set[str]:
        """Return set of completed job keys (for idempotent rerun)."""
        return {k for k, j in self.jobs.items()
                if j.state in (JobState.SUCCEEDED, JobState.FAILED_PERMANENT)}
