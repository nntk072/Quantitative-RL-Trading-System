"""Cost and token tracking for orchestra models."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from artifacts.atomic import write_text_atomic

# Approximate cost per 1M tokens (USD) — update as pricing changes
MODEL_COSTS: dict[str, dict[str, float]] = {
    "gemini/gemini-3.1-pro-preview": {"input": 1.25, "output": 10.00},
    "gemini/gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "mistral/mistral-medium-3.5": {"input": 0.40, "output": 2.00},
    "ollama/devstral-local": {"input": 0.0, "output": 0.0},
    "ollama/devstral-small": {"input": 0.0, "output": 0.0},
    "opencode/default": {"input": 0.10, "output": 0.30},
    "kilo/default": {"input": 0.10, "output": 0.30},
    "openai/gpt-5.6-luna": {"input": 0.20, "output": 1.20},
}


class CostTracker:
    """Tracks token usage and cost per model and per task."""

    def __init__(self, state_dir: Path):
        """Initialize CostTracker and its owned state.

        Args:
            state_dir: Text or path value identifying the state dir.
        """
        self.state_dir = state_dir
        self.cost_file = state_dir / "costs.json"
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load CostTracker."""
        if self.cost_file.exists():
            self._data = json.loads(self.cost_file.read_text())

    def _save(self) -> None:
        """Save CostTracker."""
        write_text_atomic(self.cost_file, json.dumps(self._data, indent=2, default=str))

    def _today(self) -> str:
        """Process CostTracker.

        Returns:
            Text returned by ``_today``.
        """
        return time.strftime("%Y-%m-%d")

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars per token).

        Args:
            text: Text or path value identifying the text.

        Returns:
            Numeric result returned by ``estimate_tokens``.
        """
        return len(text) // 4

    def record_usage(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        task_id: str | None = None,
        *,
        role: str = "general",
        success: bool = True,
        elapsed_seconds: float | None = None,
        cached_prompt_tokens: int | None = None,
        tool_invocations: int | None = None,
        retry_count: int = 0,
        token_source: str = "estimated",
    ) -> dict[str, Any]:
        """Record token usage for a model call. Returns cost breakdown.

        Args:
            model: Model used for this operation.
            prompt_tokens: Numeric value used for the prompt tokens.
            completion_tokens: Numeric value used for the completion tokens.
            task_id: Task id used by the operation described above.
            role: Orchestra role that made the model call.
            success: Whether the call returned usable output.
            elapsed_seconds: Wall time for the call when measured by the caller.
            cached_prompt_tokens: Provider-reported cached input tokens, if available.
            tool_invocations: CLI-reported tool invocations, if available.
            retry_count: Retries made before this call attempt.
            token_source: Whether token counts are estimates or provider-reported.

        Returns:
            Mapping from ``str`` keys to ``Any`` values.
        """
        today = self._today()

        configured_cost = MODEL_COSTS.get(model)
        model_cost = configured_cost or {"input": 0.10, "output": 0.30}
        input_cost = (prompt_tokens / 1_000_000) * model_cost["input"]
        output_cost = (completion_tokens / 1_000_000) * model_cost["output"]
        total_cost = round(input_cost + output_cost, 6)

        record = {
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "input_cost": round(input_cost, 6),
            "output_cost": round(output_cost, 6),
            "total_cost": total_cost,
            "task_id": task_id,
            "role": role,
            "success": success,
            "elapsed_seconds": round(elapsed_seconds, 3) if elapsed_seconds is not None else None,
            "cached_prompt_tokens": cached_prompt_tokens,
            "tool_invocations": tool_invocations,
            "retry_count": retry_count,
            "token_source": token_source,
            "cost_source": "configured" if configured_cost else "fallback estimate",
            "timestamp": time.time(),
        }

        if today not in self._data:
            self._data[today] = {"calls": [], "totals": {}}
        self._data[today]["calls"].append(record)

        totals = self._data[today]["totals"]
        totals["prompt_tokens"] = totals.get("prompt_tokens", 0) + prompt_tokens
        totals["completion_tokens"] = totals.get("completion_tokens", 0) + completion_tokens
        totals["total_cost"] = round(totals.get("total_cost", 0) + total_cost, 6)
        totals["retry_count"] = totals.get("retry_count", 0) + int(retry_count > 0)
        if elapsed_seconds is not None:
            totals["measured_elapsed_seconds"] = round(
                totals.get("measured_elapsed_seconds", 0.0) + elapsed_seconds, 3
            )
        if cached_prompt_tokens is not None:
            totals["cached_prompt_tokens"] = (
                totals.get("cached_prompt_tokens", 0) + cached_prompt_tokens
            )
        if tool_invocations is not None:
            totals["tool_invocations"] = totals.get("tool_invocations", 0) + tool_invocations

        model_key = model.replace("/", "_")
        if model_key not in totals:
            totals[model_key] = {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}
        totals[model_key]["prompt_tokens"] += prompt_tokens
        totals[model_key]["completion_tokens"] += completion_tokens
        totals[model_key]["cost"] = round(totals[model_key]["cost"] + total_cost, 6)

        self._save()
        return record

    def record_batch(
        self,
        task_id: str,
        phase: str,
        elapsed_seconds: float,
        call_seconds: list[float],
        requested: int,
        successes: int,
    ) -> dict[str, Any]:
        """Record phase-level concurrency and completion measurements.

        Args:
            task_id: Identifier of the Orchestra task.
            phase: Pipeline phase measured by this batch.
            elapsed_seconds: Wall time for the complete phase.
            call_seconds: Measured wall time for each completed model call.
            requested: Number of calls requested for the phase.
            successes: Number of calls that returned usable output.

        Returns:
            The persisted batch record.
        """
        wall = max(0.0, elapsed_seconds)
        parallelism = min(requested, len(call_seconds))
        agent_seconds = sum(call_seconds)
        record = {
            "task_id": task_id,
            "phase": phase,
            "elapsed_seconds": round(wall, 3),
            "agent_seconds": round(agent_seconds, 3),
            "requested": requested,
            "completed": len(call_seconds),
            "successes": successes,
            "parallel_efficiency": (
                round(agent_seconds / (wall * parallelism), 4)
                if wall > 0 and parallelism > 0
                else None
            ),
            "timestamp": time.time(),
        }
        today = self._today()
        self._data.setdefault(today, {"calls": [], "totals": {}}).setdefault("batches", []).append(
            record
        )
        self._save()
        return record

    def record_task_outcome(
        self, task_id: str, status: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Persist pipeline completion separately from user acceptance.

        Args:
            task_id: Identifier of the Orchestra task.
            status: Terminal pipeline status.
            metadata: Optional task identity and validation details.
        """
        today = self._today()
        day = self._data.setdefault(today, {"calls": [], "totals": {}})
        day.setdefault("tasks", {})[task_id] = {
            "pipeline_status": status,
            "accepted_completion": None,
            **(metadata or {}),
            "timestamp": time.time(),
        }
        self._save()

    def get_daily_summary(self, date: str | None = None) -> dict[str, Any]:
        """Get cost summary for a specific date (defaults to today).

        Args:
            date: Date used by the operation described above.

        Returns:
            Mapping from ``str`` keys to ``Any`` values.
        """
        date = date or self._today()
        day_data = self._data.get(date, {"calls": [], "totals": {}})
        totals = day_data.get("totals", {})
        calls = day_data.get("calls", [])
        measured = [
            call["elapsed_seconds"] for call in calls if call.get("elapsed_seconds") is not None
        ]
        cached = [
            call["cached_prompt_tokens"]
            for call in calls
            if call.get("cached_prompt_tokens") is not None
        ]
        tools = [
            call["tool_invocations"] for call in calls if call.get("tool_invocations") is not None
        ]
        return {
            "date": date,
            "total_calls": len(calls),
            "prompt_tokens": totals.get("prompt_tokens", 0),
            "completion_tokens": totals.get("completion_tokens", 0),
            "total_cost": totals.get("total_cost", 0.0),
            "cached_prompt_tokens": sum(cached) if len(cached) == len(calls) else None,
            "measured_elapsed_seconds": round(sum(measured), 3) if measured else None,
            "retry_count": totals.get("retry_count", 0),
            "tool_invocations": sum(tools) if len(tools) == len(calls) else None,
            "batches": day_data.get("batches", []),
            "models": {k: v for k, v in totals.items() if isinstance(v, dict)},
        }

    def get_monthly_summary(self, month: str | None = None) -> dict[str, Any]:
        """Get aggregated cost summary for a month.

        Args:
            month: Month used by the operation described above.

        Returns:
            Mapping from ``str`` keys to ``Any`` values.
        """
        month = month or time.strftime("%Y-%m")
        monthly: dict[str, Any] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_cost": 0.0,
            "calls": 0,
        }

        for date, day_data in self._data.items():
            if date.startswith(month):
                totals = day_data.get("totals", {})
                monthly["prompt_tokens"] += totals.get("prompt_tokens", 0)
                monthly["completion_tokens"] += totals.get("completion_tokens", 0)
                monthly["total_cost"] = round(
                    monthly["total_cost"] + totals.get("total_cost", 0.0), 6
                )
                monthly["calls"] += len(day_data.get("calls", []))

        monthly["month"] = month
        return monthly

    def get_task_cost(self, task_id: str) -> dict[str, Any] | None:
        """Get total cost for a specific task across all days.

        Args:
            task_id: Text or path value identifying the task id.

        Returns:
            Mapping from ``str`` keys to ``Any`` values.
        """
        task_calls = []
        total_cost = 0.0
        total_prompt = 0
        total_completion = 0
        total_cached: int | None = 0
        total_elapsed = 0.0
        elapsed_calls = 0
        total_retries = 0
        total_tools: int | None = 0
        successes = 0
        task_metadata: dict[str, Any] | None = None
        configured_cost_calls = 0
        fallback_cost_calls = 0
        token_sources: set[str] = set()

        for date, day_data in self._data.items():
            for call in day_data.get("calls", []):
                if call.get("task_id") == task_id:
                    task_calls.append(call)
                    total_cost += call.get("total_cost", 0)
                    total_prompt += call.get("prompt_tokens", 0)
                    total_completion += call.get("completion_tokens", 0)
                    cached = call.get("cached_prompt_tokens")
                    if cached is None:
                        total_cached = None
                    elif total_cached is not None:
                        total_cached += cached
                    elapsed = call.get("elapsed_seconds")
                    if elapsed is not None:
                        total_elapsed += elapsed
                        elapsed_calls += 1
                    tools = call.get("tool_invocations")
                    if tools is None:
                        total_tools = None
                    elif total_tools is not None:
                        total_tools += tools
                    total_retries += int(call.get("retry_count", 0) > 0)
                    successes += bool(call.get("success", True))
                    configured_cost_calls += call.get("cost_source") == "configured"
                    fallback_cost_calls += call.get("cost_source") == "fallback estimate"
                    token_sources.add(str(call.get("token_source", "unknown")))
        for day_data in reversed(list(self._data.values())):
            if task_id in day_data.get("tasks", {}):
                task_metadata = day_data["tasks"][task_id]
                break

        if not task_calls:
            return None

        return {
            "task_id": task_id,
            "calls": len(task_calls),
            "prompt_tokens": total_prompt,
            "completion_tokens": total_completion,
            "total_cost": round(total_cost, 6),
            "successful_calls": successes,
            "configured_cost_calls": configured_cost_calls,
            "fallback_cost_calls": fallback_cost_calls,
            "token_sources": sorted(token_sources),
            "cached_prompt_tokens": total_cached,
            "elapsed_seconds": round(total_elapsed, 3) if elapsed_calls else None,
            "calls_with_elapsed": elapsed_calls,
            "retry_count": total_retries,
            "tool_invocations": total_tools,
            "pipeline_status": next(
                (
                    day_data.get("tasks", {}).get(task_id, {}).get("pipeline_status")
                    for day_data in reversed(list(self._data.values()))
                    if task_id in day_data.get("tasks", {})
                ),
                None,
            ),
            "task_metadata": task_metadata,
        }
