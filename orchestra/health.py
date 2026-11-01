"""Health probes and routing status for orchestra models."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import tomllib
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from artifacts.atomic import write_text_atomic

from .model_provider_registry import Model

_HEALTH_TTL = 24 * 3600
_PROBE_TIMEOUT = 20


class RoutingStatus(StrEnum):
    """Availability states used when selecting a model for a task role."""

    AVAILABLE = "available"
    THROTTLED = "throttled"
    EXHAUSTED = "exhausted"
    AUTH_INVALID = "auth_invalid"
    MISSING = "missing"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


@dataclass
class FailureRecord:
    """Persisted summary of a model's most recent classified failure."""

    kind: str = ""
    message: str = ""
    at: float = 0.0


@dataclass
class ProbeFacts:
    """Persisted binary, auth, catalog, quota, and recent-probe observations."""

    registry_id: str
    binary_ok: bool = False
    binary_version: str | None = None
    auth_ok: bool | None = None
    in_catalog: bool | None = None
    probe_tier: int = 0
    checked_at: float = 0.0
    last_success_at: float | None = None
    last_failure: FailureRecord | None = None
    throttled_until: float | None = None
    exhausted_until: float | None = None
    disabled: bool = False
    disabled_reason: str | None = None
    consecutive_failures: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize probe facts and the nested failure record for persistence.

        Returns:
            Mapping from ``str`` keys to ``Any`` values.
        """
        d = asdict(self)
        if self.last_failure is None:
            d["last_failure"] = None
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProbeFacts:
        """Restore probe facts from a health-registry mapping.

        Args:
            data: Input data to process.

        Returns:
            Result of restore probe facts from a health-registry mapping.
        """
        lf = data.get("last_failure")
        failure = FailureRecord(**lf) if isinstance(lf, dict) else None
        return cls(
            registry_id=data.get("registry_id", ""),
            binary_ok=bool(data.get("binary_ok", False)),
            binary_version=data.get("binary_version"),
            auth_ok=data.get("auth_ok"),
            in_catalog=data.get("in_catalog"),
            probe_tier=int(data.get("probe_tier", 0)),
            checked_at=float(data.get("checked_at", 0)),
            last_success_at=data.get("last_success_at"),
            last_failure=failure,
            throttled_until=data.get("throttled_until"),
            exhausted_until=data.get("exhausted_until"),
            disabled=bool(data.get("disabled", False)),
            disabled_reason=data.get("disabled_reason"),
            consecutive_failures=int(data.get("consecutive_failures", 0)),
        )


def derive_status(facts: ProbeFacts, now: float | None = None) -> RoutingStatus:
    """Derive routing status from persisted probe facts.

    Args:
        facts: Facts used by the operation described above.
        now: Now used by the operation described above.

    Returns:
        Result of derive routing status from persisted probe facts.
    """
    now = now or time.time()
    if facts.disabled:
        return RoutingStatus.DISABLED
    if not facts.binary_ok or facts.in_catalog is False:
        return RoutingStatus.MISSING
    if facts.auth_ok is False:
        return RoutingStatus.AUTH_INVALID
    if facts.exhausted_until and now < facts.exhausted_until:
        return RoutingStatus.EXHAUSTED
    if facts.throttled_until and now < facts.throttled_until:
        return RoutingStatus.THROTTLED
    if facts.auth_ok is True and facts.in_catalog is True:
        return RoutingStatus.AVAILABLE
    return RoutingStatus.UNKNOWN


class HealthRegistry:
    """Persisted health facts per registry model id."""

    def __init__(self, state_dir: Path):
        """Initialize HealthRegistry and its owned state.

        Args:
            state_dir: Text or path value identifying the state dir.
        """
        self.state_dir = state_dir
        self.health_file = state_dir / "health.json"
        self._facts: dict[str, ProbeFacts] = {}
        self._load()

    def _load(self) -> None:
        """Load HealthRegistry."""
        if not self.health_file.exists():
            return
        raw = json.loads(self.health_file.read_text())
        for rid, data in raw.get("models", {}).items():
            data["registry_id"] = rid
            self._facts[rid] = ProbeFacts.from_dict(data)

    def _save(self) -> None:
        """Save HealthRegistry."""
        payload = {"models": {rid: f.to_dict() for rid, f in self._facts.items()}}
        write_text_atomic(self.health_file, json.dumps(payload, indent=2))

    def get(self, model: Model) -> ProbeFacts:
        """Return or initialize the persisted facts for one registry model.

        Args:
            model: Model used for this operation.

        Returns:
            Result of return or initialize the persisted facts for one registry model.
        """
        rid = model.registry_id
        if rid not in self._facts:
            self._facts[rid] = ProbeFacts(registry_id=rid)
        return self._facts[rid]

    def status(self, model: Model) -> RoutingStatus:
        """Derive the current routing state from the model's latest probe facts.

        Args:
            model: Model used for this operation.

        Returns:
            Result of derive the current routing state from the model's latest probe facts.
        """
        return derive_status(self.get(model))

    def record_failure(
        self,
        model: Model,
        kind: str,
        message: str,
        throttled_until: float | None = None,
        exhausted_until: float | None = None,
    ) -> None:
        """Persist failure details and optional throttling or exhaustion deadlines.

        Args:
            model: Model used for this operation.
            kind: Text or path value identifying the kind.
            message: Text or path value identifying the message.
            throttled_until: Throttled until used by the operation described above.
            exhausted_until: Exhausted until used by the operation described above.
        """
        facts = self.get(model)
        facts.last_failure = FailureRecord(kind=kind, message=message[:500], at=time.time())
        facts.consecutive_failures += 1
        if throttled_until:
            facts.throttled_until = throttled_until
        if exhausted_until:
            facts.exhausted_until = exhausted_until
        self._save()

    def record_success(self, model: Model) -> None:
        """Record a successful model call and clear its consecutive-failure count.

        Args:
            model: Model used for this operation.
        """
        facts = self.get(model)
        facts.last_success_at = time.time()
        facts.consecutive_failures = 0
        self._save()

    def probe_tier0(self, models: list[Model], check_version: bool = False) -> None:
        """Local-only health checks; never calls generation APIs.

        Args:
            models: Items supplied for the models, in input order.
            check_version: Whether to enable or require the check version.
        """
        for model in models:
            facts = self.get(model)
            facts.binary_ok = bool(shutil.which(model.cli))
            facts.probe_tier = 0
            facts.checked_at = time.time()
            if check_version and facts.binary_ok:
                facts.binary_version = _cli_version(model.cli)
            facts.auth_ok = _tier0_auth(model)
            if model.cli == "cline":
                facts.in_catalog = _cline_model_configured(model)
            elif model.cli == "vibe" and model.provider == "ollama":
                facts.in_catalog = _ollama_reachable()
            elif model.cli == "vibe" and model.provider == "mistral":
                facts.in_catalog = _vibe_model_in_config(model)
            else:
                facts.in_catalog = None
            if facts.auth_ok and facts.binary_ok:
                facts.last_success_at = time.time()
        self._save()

    def probe_tier1(self, models: list[Model]) -> None:
        """Network catalog probes; doctor only.

        Args:
            models: Items supplied for the models, in input order.
        """
        gemini_models = [m for m in models if m.cli == "gemini" and not m.probe_forbidden]
        if gemini_models:
            catalog = _gemini_list_models()
            for model in gemini_models:
                facts = self.get(model)
                facts.probe_tier = 1
                facts.checked_at = time.time()
                if catalog is None:
                    facts.in_catalog = None
                    facts.auth_ok = False
                else:
                    facts.auth_ok = True
                    facts.in_catalog = any(model.name in mid for mid in catalog)
        for model in models:
            if model.probe_forbidden and model.cli == "gemini":
                continue
            if model.probe_policy != "tier1" and model.cli not in ("kilo", "opencode", "vibe"):
                continue
            facts = self.get(model)
            if model.cli == "kilo":
                ok = _kilo_in_catalog(model)
                facts.probe_tier = 1
                facts.checked_at = time.time()
                facts.in_catalog = ok
            elif model.cli == "opencode":
                ok = _opencode_in_catalog(model)
                facts.probe_tier = 1
                facts.checked_at = time.time()
                facts.in_catalog = ok
            elif model.cli == "vibe" and model.env_var:
                ok = _mistral_in_catalog(model)
                facts.probe_tier = 1
                facts.checked_at = time.time()
                facts.in_catalog = ok
        self._save()

    def is_selectable(self, model: Model) -> bool:
        """Return whether health and probe policy allow routing to this model.

        Args:
            model: Model used for this operation.

        Returns:
            Whether is selectable meets the requested condition.
        """
        status = self.status(model)
        if status in (RoutingStatus.EXHAUSTED, RoutingStatus.DISABLED, RoutingStatus.MISSING):
            return False
        if status == RoutingStatus.AUTH_INVALID:
            return False
        if status == RoutingStatus.THROTTLED:
            return False
        if status == RoutingStatus.UNKNOWN and model.probe_forbidden:
            facts = self.get(model)
            return facts.binary_ok and facts.auth_ok is True
        return status in (RoutingStatus.AVAILABLE, RoutingStatus.UNKNOWN)


def _cli_version(cli: str) -> str | None:
    """Process version.

    Args:
        cli: Text or path value identifying the cli.

    Returns:
        Result of process version.
    """
    try:
        result = subprocess.run(
            [cli, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout.strip().splitlines()[0][:80]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def vibe_mistral_auth_ok() -> bool:
    """True when Vibe can reach Mistral cloud (env, ~/.vibe/.env, or whoami cache).

    Returns:
        Whether vibe mistral auth ok meets the requested condition.
    """
    if _vibe_env_api_key():
        return True
    return _vibe_whoami_authenticated()


def _vibe_config_dir() -> Path:
    """Process config dir.

    Returns:
        Path returned by ``_vibe_config_dir``.
    """
    return Path.home() / ".vibe"


def _vibe_env_api_key() -> str | None:
    """Process env api key.

    Returns:
        Result of process env api key.
    """
    key = os.environ.get("MISTRAL_API_KEY")
    if key:
        return key
    env_file = _vibe_config_dir() / ".env"
    if not env_file.exists():
        return None
    try:
        for line in env_file.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("export "):
                stripped = stripped[7:].strip()
            if "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            if name.strip() != "MISTRAL_API_KEY":
                continue
            cleaned = value.strip().strip('"').strip("'")
            if cleaned:
                return cleaned
    except OSError:
        return None
    return None


def _vibe_whoami_authenticated() -> bool:
    """Process whoami authenticated.

    Returns:
        Whether vibe whoami authenticated meets the requested condition.
    """
    cache = _vibe_config_dir() / "whoami_cache.json"
    if not cache.exists():
        return False
    try:
        data = json.loads(cache.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    for entry in data.values():
        if not isinstance(entry, dict):
            continue
        payload = entry.get("payload")
        if isinstance(payload, dict) and payload.get("customer_id"):
            return True
    return False


def _vibe_model_in_config(model: Model) -> bool | None:
    """Process model in config.

    Args:
        model: Model used for this operation.

    Returns:
        Whether vibe model in config meets the requested condition.
    """
    cfg = _vibe_config_dir() / "config.toml"
    if not cfg.exists():
        return False
    try:
        data = tomllib.loads(cfg.read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return None
    target = model.vibe_model_env()
    active = data.get("active_model")
    if isinstance(active, str) and _vibe_model_ids_match(target, active):
        return True
    for entry in data.get("models") or []:
        if not isinstance(entry, dict):
            continue
        model_id = entry.get("name") or entry.get("id") or ""
        if isinstance(model_id, str) and _vibe_model_ids_match(target, model_id):
            return True
    return False


def _vibe_model_ids_match(target: str, candidate: str) -> bool:
    """Process model ids match.

    Args:
        target: Path or filename identifying the target.
        candidate: Text or path value identifying the candidate.

    Returns:
        Whether vibe model ids match meets the requested condition.
    """
    return target == candidate or target in candidate or candidate in target


def _tier0_auth(model: Model) -> bool | None:
    """Process auth.

    Args:
        model: Model used for this operation.

    Returns:
        Whether tier0 auth meets the requested condition.
    """
    if model.cli == "vibe" and model.provider == "mistral":
        return vibe_mistral_auth_ok()
    if model.env_var:
        return bool(os.environ.get(model.env_var))
    if model.cli == "gemini":
        if os.environ.get("GEMINI_API_KEY"):
            return True
        settings = Path.home() / ".gemini" / "settings.json"
        if settings.exists():
            try:
                data = json.loads(settings.read_text())
                return bool(data.get("security", {}).get("auth", {}).get("selectedType"))
            except json.JSONDecodeError:
                return False
        return False
    if model.cli == "cline":
        return _cline_auth_ok()
    if model.cli == "vibe" and model.provider == "ollama":
        return _ollama_reachable()
    if model.cli in ("kilo", "opencode"):
        return model.is_available()
    return model.is_available()


def _cline_auth_ok() -> bool | None:
    """Process auth ok.

    Returns:
        Whether cline auth ok meets the requested condition.
    """
    path = Path.home() / ".cline" / "data" / "settings" / "providers.json"
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return False
    providers = data.get("providers") or {}
    for _pid, pdata in providers.items():
        auth = (pdata.get("settings") or {}).get("auth") or {}
        expires = auth.get("expiresAt")
        if expires and time.time() * 1000 > float(expires):
            continue
        if auth.get("accessToken") or auth.get("apiKey"):
            return True
    return False


def _cline_model_configured(model: Model) -> bool | None:
    """Process model configured.

    Args:
        model: Model used for this operation.

    Returns:
        Whether cline model configured meets the requested condition.
    """
    path = Path.home() / ".cline" / "data" / "settings" / "providers.json"
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text())
        for pdata in (data.get("providers") or {}).values():
            settings = pdata.get("settings") or {}
            if settings.get("model") == model.name:
                return True
    except json.JSONDecodeError:
        return False
    return None


def _ollama_reachable() -> bool:
    """Process reachable.

    Returns:
        Whether ollama reachable meets the requested condition.
    """
    try:
        req = Request("http://localhost:11434/api/tags", method="GET")
        with urlopen(req, timeout=2) as resp:
            return cast(bool, resp.getcode() == 200)
    except (HTTPError, URLError, OSError):
        return False


def _http_get_json(url: str, headers: dict[str, str]) -> dict[str, Any] | None:
    """Process get json.

    Args:
        url: Text or path value identifying the url.
        headers: Key-value data used for the headers.

    Returns:
        Mapping from ``str`` keys to ``Any`` values.
    """
    try:
        req = Request(url, headers=headers, method="GET")
        with urlopen(req, timeout=_PROBE_TIMEOUT) as resp:
            return cast(dict[str, Any], json.loads(resp.read().decode()))
    except (HTTPError, URLError, OSError, json.JSONDecodeError):
        return None


def _gemini_list_models() -> list[str] | None:
    """Process list models.

    Returns:
        Values returned by ``_gemini_list_models``, in the declared order.
    """
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    data = _http_get_json(
        f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
        {},
    )
    if not data:
        return None
    return [m.get("name", "") for m in data.get("models", [])]


def _mistral_in_catalog(model: Model) -> bool | None:
    """Process in catalog.

    Args:
        model: Model used for this operation.

    Returns:
        Whether mistral in catalog meets the requested condition.
    """
    key = _vibe_env_api_key() or os.environ.get(model.env_var or "MISTRAL_API_KEY")
    if not key:
        return False
    data = _http_get_json(
        "https://api.mistral.ai/v1/models",
        {"Authorization": f"Bearer {key}"},
    )
    if not data:
        return None
    ids = [m.get("id", "") for m in data.get("data", [])]
    target = model.vibe_model_env()
    return any(target in i or i in target for i in ids)


def _run_cli_json(cmd: list[str]) -> str | None:
    """Run cli json.

    Args:
        cmd: Items supplied for the cmd, in input order.

    Returns:
        Result of run cli json.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_PROBE_TIMEOUT,
        )
        if result.returncode == 0:
            return result.stdout
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _kilo_in_catalog(model: Model) -> bool | None:
    """Process in catalog.

    Args:
        model: Model used for this operation.

    Returns:
        Whether kilo in catalog meets the requested condition.
    """
    out = _run_cli_json(["kilo", "models"])
    if out is None:
        return None
    if model.name == "default":
        return "default" in out.lower() or len(out.strip()) > 0
    return model.name in out


def _opencode_in_catalog(model: Model) -> bool | None:
    """Process in catalog.

    Args:
        model: Model used for this operation.

    Returns:
        Whether opencode in catalog meets the requested condition.
    """
    out = _run_cli_json(["opencode", "models"])
    if out is None:
        return None
    if model.name == "default":
        return len(out.strip()) > 0
    return model.name in out
