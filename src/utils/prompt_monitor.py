"""Prompt monitoring for tracking LLM calls, tokens, and latency.

Enhanced with:
- Quality metrics tracking
- A/B testing integration
- Prompt Library integration
- Cost estimation
- Alerting thresholds
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict
import threading
import time

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Cost per 1K tokens (approximate, varies by provider)
# Updated periodically based on provider pricing
TOKEN_COSTS = {
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "gemini-pro": {"input": 0.00025, "output": 0.0005},
    "ollama/*": {"input": 0.0, "output": 0.0},  # Local, no cost
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost for a completion based on model and tokens."""
    # Find matching cost entry
    cost_entry = None
    for pattern, costs in TOKEN_COSTS.items():
        if pattern.endswith("/*"):
            prefix = pattern[:-2]
            if model.startswith(prefix):
                cost_entry = costs
                break
        elif pattern in model.lower():
            cost_entry = costs
            break
    
    if cost_entry is None:
        # Default to GPT-4 pricing as conservative estimate
        cost_entry = TOKEN_COSTS["gpt-4"]
    
    input_cost = (input_tokens / 1000) * cost_entry["input"]
    output_cost = (output_tokens / 1000) * cost_entry["output"]
    return input_cost + output_cost


@dataclass
class PromptCall:
    """Record of a single LLM call with enhanced tracking."""
    
    id: str
    model: str
    timestamp: datetime
    latency_ms: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    success: bool
    error: Optional[str] = None
    operation: str = "chat_completion"  # chat_completion, structured_completion, embedding
    temperature: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Enhanced tracking fields
    prompt_id: Optional[str] = None  # Prompt Library template ID
    prompt_version: Optional[str] = None  # Prompt version used
    agent_type: Optional[str] = None  # Agent that made the call
    workflow_id: Optional[str] = None  # Workflow run ID
    trace_id: Optional[str] = None  # OpenTelemetry trace ID
    
    # Quality tracking
    quality_score: Optional[float] = None  # 0.0-1.0 quality score
    quality_feedback: Optional[str] = None  # Quality evaluation feedback
    
    # A/B Testing
    ab_test_id: Optional[str] = None  # A/B test identifier
    ab_variant: Optional[str] = None  # Variant (control/treatment)
    
    # Cost tracking
    estimated_cost_usd: Optional[float] = None  # Estimated cost
    
    def __post_init__(self) -> None:
        """Calculate derived fields after initialization."""
        if self.estimated_cost_usd is None:
            self.estimated_cost_usd = estimate_cost(
                self.model, self.input_tokens, self.output_tokens
            )


@dataclass
class PromptMetrics:
    """Aggregated metrics for prompt monitoring with enhanced tracking."""
    
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    calls_by_model: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    calls_by_operation: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    tokens_by_model: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    errors_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    # Enhanced metrics
    total_cost_usd: float = 0.0
    cost_by_model: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    calls_by_agent: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    calls_by_prompt_id: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    # Quality metrics
    quality_scores: List[float] = field(default_factory=list)
    avg_quality_score: Optional[float] = None
    
    # Performance thresholds
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    
    # Time-based tracking
    calls_last_hour: int = 0
    calls_last_24h: int = 0
    tokens_last_hour: int = 0
    tokens_last_24h: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "success_rate": round(self.successful_calls / max(self.total_calls, 1), 4),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p50_latency_ms": round(self.p50_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "calls_by_model": dict(self.calls_by_model),
            "calls_by_operation": dict(self.calls_by_operation),
            "tokens_by_model": dict(self.tokens_by_model),
            "errors_by_type": dict(self.errors_by_type),
            "total_cost_usd": round(self.total_cost_usd, 4),
            "cost_by_model": {k: round(v, 4) for k, v in self.cost_by_model.items()},
            "calls_by_agent": dict(self.calls_by_agent),
            "calls_by_prompt_id": dict(self.calls_by_prompt_id),
            "avg_quality_score": round(self.avg_quality_score, 4) if self.avg_quality_score else None,
            "calls_last_hour": self.calls_last_hour,
            "calls_last_24h": self.calls_last_24h,
            "tokens_last_hour": self.tokens_last_hour,
            "tokens_last_24h": self.tokens_last_24h,
        }


@dataclass
class AlertThresholds:
    """Configurable thresholds for monitoring alerts."""
    
    latency_warning_ms: float = 5000.0  # 5 seconds
    latency_critical_ms: float = 15000.0  # 15 seconds
    error_rate_warning: float = 0.1  # 10%
    error_rate_critical: float = 0.25  # 25%
    quality_warning: float = 0.6  # Quality score below 60%
    quality_critical: float = 0.4  # Quality score below 40%
    cost_warning_usd: float = 10.0  # Per hour
    cost_critical_usd: float = 50.0  # Per hour
    tokens_warning_per_hour: int = 100000
    tokens_critical_per_hour: int = 500000


@dataclass
class MonitorAlert:
    """Alert generated by the prompt monitor."""
    
    id: str
    timestamp: datetime
    severity: str  # "warning", "critical"
    alert_type: str  # "latency", "error_rate", "quality", "cost", "tokens"
    message: str
    current_value: float
    threshold_value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class PromptMonitor:
    """Monitor and track LLM prompt calls with enhanced observability.
    
    Thread-safe singleton that tracks:
    - Call counts (total, success, failure)
    - Token usage (input, output, total)
    - Latency (per call, average, percentiles)
    - Errors by type
    - Breakdown by model, operation, agent, and prompt
    - Cost estimation and tracking
    - Quality metrics
    - Alerting for threshold violations
    
    Integrates with:
    - Prompt Library for template tracking
    - OpenTelemetry for distributed tracing
    """
    
    _instance: Optional["PromptMonitor"] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> "PromptMonitor":
        """Singleton pattern for global monitoring."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize the prompt monitor."""
        if self._initialized:
            return
        
        self._calls: List[PromptCall] = []
        self._latencies: List[float] = []  # For percentile calculation
        self._metrics = PromptMetrics()
        self._call_lock = threading.Lock()
        self._call_counter = 0
        self._max_history = 1000  # Keep last N calls in memory
        self._max_latencies = 10000  # For percentile calculation
        self._initialized = True
        
        # Alert configuration
        self._thresholds = AlertThresholds()
        self._alerts: List[MonitorAlert] = []
        self._alert_handlers: List[Callable[[MonitorAlert], None]] = []
        
        # Hourly tracking for rate-based alerts
        self._hourly_calls: List[datetime] = []
        self._hourly_tokens: List[tuple[datetime, int]] = []
        self._hourly_cost: List[tuple[datetime, float]] = []
        
        logger.info("prompt_monitor_initialized")
    
    def _generate_call_id(self) -> str:
        """Generate unique call ID."""
        with self._call_lock:
            self._call_counter += 1
            return f"call-{self._call_counter}-{int(time.time() * 1000)}"
    
    def configure_thresholds(self, thresholds: AlertThresholds) -> None:
        """Configure alerting thresholds.
        
        Args:
            thresholds: AlertThresholds configuration.
        """
        self._thresholds = thresholds
        logger.info("alert_thresholds_configured", thresholds=thresholds)
    
    def add_alert_handler(self, handler: Callable[[MonitorAlert], None]) -> None:
        """Add an alert handler callback.
        
        Args:
            handler: Callback function that receives MonitorAlert.
        """
        self._alert_handlers.append(handler)
    
    def _emit_alert(self, alert: MonitorAlert) -> None:
        """Emit an alert to all handlers."""
        self._alerts.append(alert)
        if len(self._alerts) > 100:
            self._alerts = self._alerts[-100:]
        
        for handler in self._alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error("alert_handler_error", error=str(e))
        
        logger.warning(
            "prompt_monitor_alert",
            severity=alert.severity,
            alert_type=alert.alert_type,
            message=alert.message,
            current_value=alert.current_value,
            threshold_value=alert.threshold_value,
        )
    
    def _check_alerts(self, call: PromptCall) -> None:
        """Check for alert conditions after a call."""
        now = datetime.now()
        alert_id = f"alert-{int(time.time() * 1000)}"
        
        # Latency alert
        if call.latency_ms >= self._thresholds.latency_critical_ms:
            self._emit_alert(MonitorAlert(
                id=f"{alert_id}-latency",
                timestamp=now,
                severity="critical",
                alert_type="latency",
                message=f"Critical latency: {call.latency_ms:.0f}ms for {call.model}",
                current_value=call.latency_ms,
                threshold_value=self._thresholds.latency_critical_ms,
                metadata={"model": call.model, "call_id": call.id},
            ))
        elif call.latency_ms >= self._thresholds.latency_warning_ms:
            self._emit_alert(MonitorAlert(
                id=f"{alert_id}-latency",
                timestamp=now,
                severity="warning",
                alert_type="latency",
                message=f"High latency: {call.latency_ms:.0f}ms for {call.model}",
                current_value=call.latency_ms,
                threshold_value=self._thresholds.latency_warning_ms,
                metadata={"model": call.model, "call_id": call.id},
            ))
        
        # Error rate alert (check rolling window)
        if self._metrics.total_calls >= 10:
            error_rate = self._metrics.failed_calls / self._metrics.total_calls
            if error_rate >= self._thresholds.error_rate_critical:
                self._emit_alert(MonitorAlert(
                    id=f"{alert_id}-error-rate",
                    timestamp=now,
                    severity="critical",
                    alert_type="error_rate",
                    message=f"Critical error rate: {error_rate:.1%}",
                    current_value=error_rate,
                    threshold_value=self._thresholds.error_rate_critical,
                ))
            elif error_rate >= self._thresholds.error_rate_warning:
                self._emit_alert(MonitorAlert(
                    id=f"{alert_id}-error-rate",
                    timestamp=now,
                    severity="warning",
                    alert_type="error_rate",
                    message=f"Elevated error rate: {error_rate:.1%}",
                    current_value=error_rate,
                    threshold_value=self._thresholds.error_rate_warning,
                ))
        
        # Quality alert
        if call.quality_score is not None:
            if call.quality_score <= self._thresholds.quality_critical:
                self._emit_alert(MonitorAlert(
                    id=f"{alert_id}-quality",
                    timestamp=now,
                    severity="critical",
                    alert_type="quality",
                    message=f"Critical quality score: {call.quality_score:.2f}",
                    current_value=call.quality_score,
                    threshold_value=self._thresholds.quality_critical,
                    metadata={"call_id": call.id, "prompt_id": call.prompt_id},
                ))
            elif call.quality_score <= self._thresholds.quality_warning:
                self._emit_alert(MonitorAlert(
                    id=f"{alert_id}-quality",
                    timestamp=now,
                    severity="warning",
                    alert_type="quality",
                    message=f"Low quality score: {call.quality_score:.2f}",
                    current_value=call.quality_score,
                    threshold_value=self._thresholds.quality_warning,
                    metadata={"call_id": call.id, "prompt_id": call.prompt_id},
                ))
    
    def _update_percentiles(self) -> None:
        """Update latency percentiles."""
        if not self._latencies:
            return
        
        sorted_latencies = sorted(self._latencies)
        n = len(sorted_latencies)
        
        self._metrics.p50_latency_ms = sorted_latencies[int(n * 0.5)]
        self._metrics.p95_latency_ms = sorted_latencies[min(int(n * 0.95), n - 1)]
        self._metrics.p99_latency_ms = sorted_latencies[min(int(n * 0.99), n - 1)]
    
    def _update_time_based_metrics(self) -> None:
        """Update time-based metrics (last hour, last 24h)."""
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(hours=24)
        
        # Clean old entries and count
        self._hourly_calls = [t for t in self._hourly_calls if t > day_ago]
        self._hourly_tokens = [(t, n) for t, n in self._hourly_tokens if t > day_ago]
        
        self._metrics.calls_last_hour = sum(1 for t in self._hourly_calls if t > hour_ago)
        self._metrics.calls_last_24h = len(self._hourly_calls)
        
        self._metrics.tokens_last_hour = sum(n for t, n in self._hourly_tokens if t > hour_ago)
        self._metrics.tokens_last_24h = sum(n for _, n in self._hourly_tokens)
    
    def record_call(
        self,
        model: str,
        operation: str,
        latency_ms: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        success: bool = True,
        error: Optional[str] = None,
        temperature: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        # Enhanced tracking parameters
        prompt_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
        agent_type: Optional[str] = None,
        workflow_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        quality_score: Optional[float] = None,
        quality_feedback: Optional[str] = None,
        ab_test_id: Optional[str] = None,
        ab_variant: Optional[str] = None,
    ) -> PromptCall:
        """Record an LLM call with enhanced tracking.
        
        Args:
            model: Model name (e.g., "ollama/llama3", "gpt-4").
            operation: Operation type (chat_completion, structured_completion, embedding).
            latency_ms: Call latency in milliseconds.
            input_tokens: Number of input tokens.
            output_tokens: Number of output tokens.
            success: Whether the call succeeded.
            error: Error message if failed.
            temperature: Temperature setting if applicable.
            metadata: Additional metadata.
            prompt_id: Prompt Library template ID.
            prompt_version: Prompt version used.
            agent_type: Agent that made the call.
            workflow_id: Workflow run ID.
            trace_id: OpenTelemetry trace ID.
            quality_score: Quality score (0.0-1.0).
            quality_feedback: Quality evaluation feedback.
            ab_test_id: A/B test identifier.
            ab_variant: A/B test variant.
            
        Returns:
            The recorded PromptCall.
        """
        call = PromptCall(
            id=self._generate_call_id(),
            model=model,
            timestamp=datetime.now(),
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            success=success,
            error=error,
            operation=operation,
            temperature=temperature,
            metadata=metadata or {},
            prompt_id=prompt_id,
            prompt_version=prompt_version,
            agent_type=agent_type,
            workflow_id=workflow_id,
            trace_id=trace_id,
            quality_score=quality_score,
            quality_feedback=quality_feedback,
            ab_test_id=ab_test_id,
            ab_variant=ab_variant,
        )
        
        with self._call_lock:
            # Add to history (with limit)
            self._calls.append(call)
            if len(self._calls) > self._max_history:
                self._calls = self._calls[-self._max_history:]
            
            # Track latency for percentiles
            self._latencies.append(latency_ms)
            if len(self._latencies) > self._max_latencies:
                self._latencies = self._latencies[-self._max_latencies:]
            
            # Update aggregated metrics
            self._metrics.total_calls += 1
            if success:
                self._metrics.successful_calls += 1
            else:
                self._metrics.failed_calls += 1
                if error:
                    error_type = error.split(":")[0] if ":" in error else error[:50]
                    self._metrics.errors_by_type[error_type] += 1
            
            self._metrics.total_input_tokens += input_tokens
            self._metrics.total_output_tokens += output_tokens
            self._metrics.total_tokens += call.total_tokens
            self._metrics.total_latency_ms += latency_ms
            
            if self._metrics.total_calls > 0:
                self._metrics.avg_latency_ms = (
                    self._metrics.total_latency_ms / self._metrics.total_calls
                )
            
            self._metrics.calls_by_model[model] += 1
            self._metrics.calls_by_operation[operation] += 1
            self._metrics.tokens_by_model[model] += call.total_tokens
            
            # Enhanced metrics
            if call.estimated_cost_usd:
                self._metrics.total_cost_usd += call.estimated_cost_usd
                self._metrics.cost_by_model[model] += call.estimated_cost_usd
            
            if agent_type:
                self._metrics.calls_by_agent[agent_type] += 1
            
            if prompt_id:
                self._metrics.calls_by_prompt_id[prompt_id] += 1
            
            if quality_score is not None:
                self._metrics.quality_scores.append(quality_score)
                if len(self._metrics.quality_scores) > 1000:
                    self._metrics.quality_scores = self._metrics.quality_scores[-1000:]
                self._metrics.avg_quality_score = (
                    sum(self._metrics.quality_scores) / len(self._metrics.quality_scores)
                )
            
            # Time-based tracking
            now = datetime.now()
            self._hourly_calls.append(now)
            self._hourly_tokens.append((now, call.total_tokens))
            if call.estimated_cost_usd:
                self._hourly_cost.append((now, call.estimated_cost_usd))
            
            # Update percentiles and time-based metrics
            self._update_percentiles()
            self._update_time_based_metrics()
        
        # Check for alerts (outside lock)
        self._check_alerts(call)
        
        # Log the call
        logger.info(
            "prompt_call_recorded",
            call_id=call.id,
            model=model,
            operation=operation,
            latency_ms=round(latency_ms, 2),
            tokens=call.total_tokens,
            success=success,
            prompt_id=prompt_id,
            agent_type=agent_type,
            cost_usd=round(call.estimated_cost_usd or 0, 4),
        )
        
        return call
    
    def record_quality_feedback(
        self,
        call_id: str,
        quality_score: float,
        feedback: Optional[str] = None,
    ) -> bool:
        """Record quality feedback for a previous call.
        
        Args:
            call_id: Call ID to update.
            quality_score: Quality score (0.0-1.0).
            feedback: Optional feedback text.
            
        Returns:
            True if call found and updated, False otherwise.
        """
        with self._call_lock:
            for call in self._calls:
                if call.id == call_id:
                    call.quality_score = quality_score
                    call.quality_feedback = feedback
                    
                    # Update metrics
                    self._metrics.quality_scores.append(quality_score)
                    if len(self._metrics.quality_scores) > 1000:
                        self._metrics.quality_scores = self._metrics.quality_scores[-1000:]
                    self._metrics.avg_quality_score = (
                        sum(self._metrics.quality_scores) / len(self._metrics.quality_scores)
                    )
                    
                    logger.info(
                        "quality_feedback_recorded",
                        call_id=call_id,
                        quality_score=quality_score,
                    )
                    return True
        return False
    
    def get_metrics(self) -> PromptMetrics:
        """Get current aggregated metrics."""
        with self._call_lock:
            return self._metrics
    
    def get_recent_calls(
        self,
        limit: int = 50,
        model: Optional[str] = None,
        agent_type: Optional[str] = None,
        prompt_id: Optional[str] = None,
        success_only: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent call history with optional filtering.
        
        Args:
            limit: Maximum number of calls to return.
            model: Filter by model name.
            agent_type: Filter by agent type.
            prompt_id: Filter by prompt ID.
            success_only: Filter by success status.
            
        Returns:
            List of call records as dictionaries.
        """
        with self._call_lock:
            # Apply filters
            filtered_calls = self._calls
            
            if model is not None:
                filtered_calls = [c for c in filtered_calls if c.model == model]
            if agent_type is not None:
                filtered_calls = [c for c in filtered_calls if c.agent_type == agent_type]
            if prompt_id is not None:
                filtered_calls = [c for c in filtered_calls if c.prompt_id == prompt_id]
            if success_only is not None:
                filtered_calls = [c for c in filtered_calls if c.success == success_only]
            
            calls = filtered_calls[-limit:] if limit else filtered_calls
            return [
                {
                    "id": c.id,
                    "model": c.model,
                    "timestamp": c.timestamp.isoformat(),
                    "latency_ms": round(c.latency_ms, 2),
                    "input_tokens": c.input_tokens,
                    "output_tokens": c.output_tokens,
                    "total_tokens": c.total_tokens,
                    "success": c.success,
                    "error": c.error,
                    "operation": c.operation,
                    "temperature": c.temperature,
                    "prompt_id": c.prompt_id,
                    "prompt_version": c.prompt_version,
                    "agent_type": c.agent_type,
                    "workflow_id": c.workflow_id,
                    "trace_id": c.trace_id,
                    "quality_score": c.quality_score,
                    "estimated_cost_usd": round(c.estimated_cost_usd or 0, 4),
                    "ab_test_id": c.ab_test_id,
                    "ab_variant": c.ab_variant,
                }
                for c in reversed(calls)  # Most recent first
            ]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of prompt monitoring stats.
        
        Returns:
            Dictionary with metrics summary, recent calls, and alerts.
        """
        return {
            "metrics": self.get_metrics().to_dict(),
            "recent_calls": self.get_recent_calls(limit=10),
            "recent_alerts": [
                {
                    "id": a.id,
                    "timestamp": a.timestamp.isoformat(),
                    "severity": a.severity,
                    "alert_type": a.alert_type,
                    "message": a.message,
                    "current_value": a.current_value,
                    "threshold_value": a.threshold_value,
                }
                for a in self._alerts[-10:]
            ],
            "timestamp": datetime.now().isoformat(),
        }
    
    def get_alerts(
        self,
        severity: Optional[str] = None,
        alert_type: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get recent alerts with optional filtering.
        
        Args:
            severity: Filter by severity ("warning", "critical").
            alert_type: Filter by type ("latency", "error_rate", etc.).
            since: Only include alerts after this time.
            limit: Maximum number to return.
            
        Returns:
            List of alert records.
        """
        alerts = self._alerts
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        if alert_type:
            alerts = [a for a in alerts if a.alert_type == alert_type]
        if since:
            alerts = [a for a in alerts if a.timestamp > since]
        
        return [
            {
                "id": a.id,
                "timestamp": a.timestamp.isoformat(),
                "severity": a.severity,
                "alert_type": a.alert_type,
                "message": a.message,
                "current_value": a.current_value,
                "threshold_value": a.threshold_value,
                "metadata": a.metadata,
            }
            for a in alerts[-limit:]
        ]
    
    def get_agent_metrics(self, agent_type: str) -> Dict[str, Any]:
        """Get metrics for a specific agent type.
        
        Args:
            agent_type: Agent type to get metrics for.
            
        Returns:
            Dictionary with agent-specific metrics.
        """
        with self._call_lock:
            agent_calls = [c for c in self._calls if c.agent_type == agent_type]
            
            if not agent_calls:
                return {
                    "agent_type": agent_type,
                    "total_calls": 0,
                    "success_rate": 0.0,
                    "avg_latency_ms": 0.0,
                    "total_tokens": 0,
                    "total_cost_usd": 0.0,
                    "avg_quality_score": None,
                }
            
            successful = sum(1 for c in agent_calls if c.success)
            total_tokens = sum(c.total_tokens for c in agent_calls)
            total_cost = sum(c.estimated_cost_usd or 0 for c in agent_calls)
            quality_scores = [c.quality_score for c in agent_calls if c.quality_score is not None]
            
            return {
                "agent_type": agent_type,
                "total_calls": len(agent_calls),
                "success_rate": successful / len(agent_calls),
                "avg_latency_ms": sum(c.latency_ms for c in agent_calls) / len(agent_calls),
                "total_tokens": total_tokens,
                "total_cost_usd": round(total_cost, 4),
                "avg_quality_score": (
                    sum(quality_scores) / len(quality_scores)
                    if quality_scores else None
                ),
                "models_used": list(set(c.model for c in agent_calls)),
                "prompts_used": list(set(c.prompt_id for c in agent_calls if c.prompt_id)),
            }
    
    def get_prompt_metrics(self, prompt_id: str) -> Dict[str, Any]:
        """Get metrics for a specific prompt template.
        
        Args:
            prompt_id: Prompt template ID.
            
        Returns:
            Dictionary with prompt-specific metrics.
        """
        with self._call_lock:
            prompt_calls = [c for c in self._calls if c.prompt_id == prompt_id]
            
            if not prompt_calls:
                return {
                    "prompt_id": prompt_id,
                    "total_calls": 0,
                    "success_rate": 0.0,
                    "avg_latency_ms": 0.0,
                    "total_tokens": 0,
                    "versions_used": [],
                    "avg_quality_score": None,
                }
            
            successful = sum(1 for c in prompt_calls if c.success)
            quality_scores = [c.quality_score for c in prompt_calls if c.quality_score is not None]
            versions = list(set(c.prompt_version for c in prompt_calls if c.prompt_version))
            
            # Version-specific metrics
            version_metrics = {}
            for version in versions:
                version_calls = [c for c in prompt_calls if c.prompt_version == version]
                version_successful = sum(1 for c in version_calls if c.success)
                version_quality = [c.quality_score for c in version_calls if c.quality_score is not None]
                version_metrics[version] = {
                    "total_calls": len(version_calls),
                    "success_rate": version_successful / len(version_calls) if version_calls else 0,
                    "avg_latency_ms": sum(c.latency_ms for c in version_calls) / len(version_calls) if version_calls else 0,
                    "avg_quality_score": sum(version_quality) / len(version_quality) if version_quality else None,
                }
            
            return {
                "prompt_id": prompt_id,
                "total_calls": len(prompt_calls),
                "success_rate": successful / len(prompt_calls),
                "avg_latency_ms": sum(c.latency_ms for c in prompt_calls) / len(prompt_calls),
                "total_tokens": sum(c.total_tokens for c in prompt_calls),
                "versions_used": versions,
                "version_metrics": version_metrics,
                "avg_quality_score": (
                    sum(quality_scores) / len(quality_scores)
                    if quality_scores else None
                ),
                "agents_using": list(set(c.agent_type for c in prompt_calls if c.agent_type)),
            }
    
    def get_ab_test_results(self, ab_test_id: str) -> Dict[str, Any]:
        """Get A/B test results for a specific test.
        
        Args:
            ab_test_id: A/B test identifier.
            
        Returns:
            Dictionary with A/B test results.
        """
        with self._call_lock:
            test_calls = [c for c in self._calls if c.ab_test_id == ab_test_id]
            
            if not test_calls:
                return {
                    "ab_test_id": ab_test_id,
                    "total_samples": 0,
                    "variants": {},
                }
            
            # Group by variant
            variants: Dict[str, List[PromptCall]] = {}
            for call in test_calls:
                variant = call.ab_variant or "unknown"
                if variant not in variants:
                    variants[variant] = []
                variants[variant].append(call)
            
            # Calculate metrics per variant
            variant_metrics = {}
            for variant, calls in variants.items():
                successful = sum(1 for c in calls if c.success)
                quality_scores = [c.quality_score for c in calls if c.quality_score is not None]
                
                variant_metrics[variant] = {
                    "sample_size": len(calls),
                    "success_rate": successful / len(calls) if calls else 0,
                    "avg_latency_ms": sum(c.latency_ms for c in calls) / len(calls) if calls else 0,
                    "avg_quality_score": (
                        sum(quality_scores) / len(quality_scores)
                        if quality_scores else None
                    ),
                    "total_cost_usd": round(sum(c.estimated_cost_usd or 0 for c in calls), 4),
                }
            
            return {
                "ab_test_id": ab_test_id,
                "total_samples": len(test_calls),
                "variants": variant_metrics,
            }
    
    def reset(self) -> None:
        """Reset all metrics and history."""
        with self._call_lock:
            self._calls = []
            self._latencies = []
            self._metrics = PromptMetrics()
            self._call_counter = 0
            self._alerts = []
            self._hourly_calls = []
            self._hourly_tokens = []
            self._hourly_cost = []
        
        logger.info("prompt_monitor_reset")
    
    def export_metrics_for_otel(self) -> Dict[str, Any]:
        """Export metrics in a format suitable for OpenTelemetry.
        
        Returns:
            Dictionary with metrics formatted for OTLP export.
        """
        metrics = self._metrics
        return {
            "synapse.prompt.calls.total": metrics.total_calls,
            "synapse.prompt.calls.success": metrics.successful_calls,
            "synapse.prompt.calls.failed": metrics.failed_calls,
            "synapse.prompt.tokens.input": metrics.total_input_tokens,
            "synapse.prompt.tokens.output": metrics.total_output_tokens,
            "synapse.prompt.latency.avg_ms": metrics.avg_latency_ms,
            "synapse.prompt.latency.p50_ms": metrics.p50_latency_ms,
            "synapse.prompt.latency.p95_ms": metrics.p95_latency_ms,
            "synapse.prompt.latency.p99_ms": metrics.p99_latency_ms,
            "synapse.prompt.cost.total_usd": metrics.total_cost_usd,
            "synapse.prompt.quality.avg": metrics.avg_quality_score or 0.0,
        }


# Global singleton instance
_monitor: Optional[PromptMonitor] = None


def get_prompt_monitor() -> PromptMonitor:
    """Get the global prompt monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = PromptMonitor()
    return _monitor


def record_prompt_call(
    model: str,
    operation: str,
    latency_ms: float,
    input_tokens: int = 0,
    output_tokens: int = 0,
    success: bool = True,
    error: Optional[str] = None,
    prompt_id: Optional[str] = None,
    prompt_version: Optional[str] = None,
    agent_type: Optional[str] = None,
    workflow_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    quality_score: Optional[float] = None,
    quality_feedback: Optional[str] = None,
    ab_test_id: Optional[str] = None,
    ab_variant: Optional[str] = None,
    **kwargs: Any,
) -> PromptCall:
    """Convenience function to record a prompt call with enhanced tracking.
    
    Args:
        model: Model name.
        operation: Operation type.
        latency_ms: Latency in milliseconds.
        input_tokens: Input token count.
        output_tokens: Output token count.
        success: Whether call succeeded.
        error: Error message if failed.
        prompt_id: Prompt Library template ID.
        prompt_version: Prompt version used.
        agent_type: Agent that made the call.
        workflow_id: Workflow run ID.
        trace_id: OpenTelemetry trace ID.
        quality_score: Quality score (0.0-1.0).
        quality_feedback: Quality evaluation feedback.
        ab_test_id: A/B test identifier.
        ab_variant: A/B test variant.
        **kwargs: Additional metadata.
        
    Returns:
        The recorded PromptCall.
    """
    return get_prompt_monitor().record_call(
        model=model,
        operation=operation,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        success=success,
        error=error,
        metadata=kwargs,
        prompt_id=prompt_id,
        prompt_version=prompt_version,
        agent_type=agent_type,
        workflow_id=workflow_id,
        trace_id=trace_id,
        quality_score=quality_score,
        quality_feedback=quality_feedback,
        ab_test_id=ab_test_id,
        ab_variant=ab_variant,
    )


def get_prompt_metrics(prompt_id: str) -> Dict[str, Any]:
    """Get metrics for a specific prompt template.
    
    Args:
        prompt_id: Prompt template ID.
        
    Returns:
        Dictionary with prompt-specific metrics.
    """
    return get_prompt_monitor().get_prompt_metrics(prompt_id)


def get_agent_metrics(agent_type: str) -> Dict[str, Any]:
    """Get metrics for a specific agent type.
    
    Args:
        agent_type: Agent type.
        
    Returns:
        Dictionary with agent-specific metrics.
    """
    return get_prompt_monitor().get_agent_metrics(agent_type)


def get_ab_test_results(ab_test_id: str) -> Dict[str, Any]:
    """Get results for an A/B test.
    
    Args:
        ab_test_id: A/B test identifier.
        
    Returns:
        Dictionary with A/B test results.
    """
    return get_prompt_monitor().get_ab_test_results(ab_test_id)
