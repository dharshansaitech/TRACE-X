# backend/api/schemas/repair.py
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RepairType(str, Enum):
    PROMPT_EDIT = "prompt_edit"
    TOOL_CONFIG_CHANGE = "tool_config_change"
    RETRY_POLICY_CHANGE = "retry_policy_change"
    CONTEXT_INJECTION = "context_injection"
    ORCHESTRATION_FIX = "orchestration_fix"
    PARAMETER_TUNING = "parameter_tuning"
    DATA_VALIDATION = "data_validation"
    FALLBACK_ADDITION = "fallback_addition"
    TIMEOUT_ADJUSTMENT = "timeout_adjustment"
    MODEL_SWAP = "model_swap"


class RepairStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    APPLIED = "applied"
    VALIDATED = "validated"
    REJECTED = "rejected"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class DiffLine(BaseModel):
    """A single line in a diff."""
    line_number: int
    content: str
    change_type: str  # "added", "removed", "context"


class RepairDiff(BaseModel):
    """Before/after diff for a repair artifact."""
    file_path: str | None = None
    target_type: str  # "prompt", "tool_config", "agent_config", "code"
    before: str
    after: str
    diff_lines: list[DiffLine] = Field(default_factory=list)
    description: str = ""


class TestCase(BaseModel):
    """A test case for validating a repair."""
    test_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    input_payload: dict[str, Any] = Field(default_factory=dict)
    expected_output_pattern: str | None = None
    expected_behavior: str
    failure_scenario: str
    timeout_seconds: float = 30.0
    # Results (filled after running)
    passed: bool | None = None
    actual_output: Any | None = None
    error: str | None = None
    run_duration_ms: float | None = None


class RepairArtifact(BaseModel):
    """A complete repair artifact for a diagnosed failure."""
    repair_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str
    diagnosis_id: str
    agent_id: str

    # Repair details
    repair_type: RepairType
    title: str
    description: str
    rationale: str  # Why this repair addresses the root cause

    # The actual repair
    diff: RepairDiff
    implementation_instructions: list[str] = Field(default_factory=list)

    # Test cases
    test_cases: list[TestCase] = Field(default_factory=list)

    # Confidence and risk
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: str = "low"  # "low", "medium", "high"
    side_effects: list[str] = Field(default_factory=list)
    rollback_instructions: str | None = None

    # Status tracking
    status: RepairStatus = RepairStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: datetime | None = None
    applied_at: datetime | None = None
    applied_by: str | None = None
    rolled_back_at: datetime | None = None
    rolled_back_by: str | None = None

    # Validation results
    validation_passed: bool | None = None
    validation_score: float | None = None
    validation_notes: str | None = None
    tests_passed: int = 0
    tests_failed: int = 0
    tests_total: int = 0

    # LLM metadata
    model_used: str = "gemini-2.0-flash"
    generation_duration_ms: float | None = None


class RepairApproveRequest(BaseModel):
    """Request to approve a repair."""
    approved_by: str
    notes: str | None = None


class RepairApplyRequest(BaseModel):
    """Request to apply an approved repair."""
    applied_by: str
    dry_run: bool = False


class RepairRollbackRequest(BaseModel):
    """Request to roll back an applied repair."""
    rolled_back_by: str
    reason: str


class RepairListResponse(BaseModel):
    """List of repairs with pagination."""
    repairs: list[RepairArtifact]
    total: int
    pending_count: int
    approved_count: int
    applied_count: int


class RepairSummary(BaseModel):
    """Lightweight repair summary for listings."""
    repair_id: str
    trace_id: str
    repair_type: RepairType
    title: str
    confidence: float
    risk_level: str
    status: RepairStatus
    created_at: datetime
    one_line_description: str
