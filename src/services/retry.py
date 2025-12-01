"""Retry logic with exponential backoff and circuit breaker.

Provides robust error handling for transient failures during HTTP requests.
"""

import asyncio
import functools
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Set, Type, TypeVar

import httpx
from rich.console import Console

from ..config import get_settings

console = Console()

T = TypeVar("T")


class CircuitState(Enum):
    """States for the circuit breaker."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


# HTTP status codes that should trigger retry
RETRYABLE_STATUS_CODES: Set[int] = {
    408,  # Request Timeout
    429,  # Too Many Requests
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
}

# Exceptions that should trigger retry
RETRYABLE_EXCEPTIONS: tuple[Type[Exception], ...] = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.ReadError,
    httpx.WriteError,
    ConnectionError,
    asyncio.TimeoutError,
)


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    initial_delay: float = 1.0
    backoff_factor: float = 2.0
    max_delay: float = 60.0
    jitter: bool = True
    retryable_status_codes: Set[int] = field(
        default_factory=lambda: RETRYABLE_STATUS_CODES.copy()
    )

    @classmethod
    def from_settings(cls) -> "RetryConfig":
        """Create config from application settings."""
        settings = get_settings()
        return cls(
            max_attempts=settings.max_retries,
            initial_delay=settings.retry_initial_delay,
            backoff_factor=settings.retry_backoff_factor,
        )


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes before closing
    timeout: float = 60.0  # Seconds before trying again


class CircuitBreaker:
    """Circuit breaker to prevent cascading failures.

    Opens after consecutive failures to allow service recovery,
    then gradually tests if the service has recovered.
    """

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None

    def can_execute(self) -> bool:
        """Check if request should be allowed."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if self.last_failure_time:
                elapsed = time.monotonic() - self.last_failure_time
                if elapsed >= self.config.timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    console.print("[yellow]Circuit breaker: half-open, testing...[/yellow]")
                    return True
            return False

        # HALF_OPEN - allow one request to test
        return True

    def record_success(self) -> None:
        """Record a successful request."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                console.print("[green]Circuit breaker: closed (recovered)[/green]")
        else:
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record a failed request."""
        self.failure_count += 1
        self.last_failure_time = time.monotonic()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            console.print("[red]Circuit breaker: open (still failing)[/red]")
        elif self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            console.print(
                f"[red]Circuit breaker: open after {self.failure_count} failures[/red]"
            )


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""

    pass


class MaxRetriesExceededError(Exception):
    """Raised when maximum retry attempts are exceeded."""

    def __init__(self, message: str, last_exception: Optional[Exception] = None):
        super().__init__(message)
        self.last_exception = last_exception


def calculate_delay(
    attempt: int,
    config: RetryConfig,
) -> float:
    """Calculate delay before next retry with optional jitter.

    Args:
        attempt: Current attempt number (0-indexed)
        config: Retry configuration

    Returns:
        Delay in seconds
    """
    delay = config.initial_delay * (config.backoff_factor ** attempt)
    delay = min(delay, config.max_delay)

    if config.jitter:
        # Add random jitter (±25%)
        jitter_range = delay * 0.25
        delay += random.uniform(-jitter_range, jitter_range)

    return max(0, delay)


def is_retryable_response(response: httpx.Response, config: RetryConfig) -> bool:
    """Check if an HTTP response should trigger a retry."""
    return response.status_code in config.retryable_status_codes


def is_retryable_exception(exc: Exception) -> bool:
    """Check if an exception should trigger a retry."""
    return isinstance(exc, RETRYABLE_EXCEPTIONS)


def with_retry(
    config: Optional[RetryConfig] = None,
    circuit_breaker: Optional[CircuitBreaker] = None,
) -> Callable:
    """Decorator for adding retry logic to async functions.

    Args:
        config: Retry configuration (uses settings defaults if not provided)
        circuit_breaker: Optional circuit breaker for failure protection

    Usage:
        @with_retry()
        async def fetch_page(url: str) -> str:
            ...

        # With custom config
        @with_retry(RetryConfig(max_attempts=5, initial_delay=2.0))
        async def fetch_page(url: str) -> str:
            ...
    """
    _config = config or RetryConfig.from_settings()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Check circuit breaker
            if circuit_breaker and not circuit_breaker.can_execute():
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is open for {func.__name__}"
                )

            last_exception: Optional[Exception] = None

            for attempt in range(_config.max_attempts):
                try:
                    result = await func(*args, **kwargs)

                    # Check for retryable HTTP response
                    if isinstance(result, httpx.Response):
                        if is_retryable_response(result, _config):
                            if attempt < _config.max_attempts - 1:
                                delay = calculate_delay(attempt, _config)
                                console.print(
                                    f"[yellow]Retry {attempt + 1}/{_config.max_attempts} "
                                    f"for status {result.status_code}, waiting {delay:.1f}s[/yellow]"
                                )
                                await asyncio.sleep(delay)
                                continue

                    # Success
                    if circuit_breaker:
                        circuit_breaker.record_success()
                    return result

                except RETRYABLE_EXCEPTIONS as e:
                    last_exception = e

                    if circuit_breaker:
                        circuit_breaker.record_failure()

                    if attempt < _config.max_attempts - 1:
                        delay = calculate_delay(attempt, _config)
                        console.print(
                            f"[yellow]Retry {attempt + 1}/{_config.max_attempts} "
                            f"after {type(e).__name__}, waiting {delay:.1f}s[/yellow]"
                        )
                        await asyncio.sleep(delay)
                    else:
                        raise MaxRetriesExceededError(
                            f"Max retries ({_config.max_attempts}) exceeded for {func.__name__}",
                            last_exception=e,
                        ) from e

                except Exception as e:
                    # Non-retryable exception
                    if circuit_breaker:
                        circuit_breaker.record_failure()
                    raise

            # Should not reach here, but just in case
            raise MaxRetriesExceededError(
                f"Max retries ({_config.max_attempts}) exceeded",
                last_exception=last_exception,
            )

        return wrapper

    return decorator


async def retry_async(
    func: Callable[..., T],
    *args,
    config: Optional[RetryConfig] = None,
    **kwargs,
) -> T:
    """Execute an async function with retry logic.

    Alternative to decorator for one-off retries.

    Args:
        func: Async function to execute
        *args: Positional arguments for func
        config: Retry configuration
        **kwargs: Keyword arguments for func

    Returns:
        Result from func

    Usage:
        result = await retry_async(fetch_page, url, config=RetryConfig(max_attempts=5))
    """

    @with_retry(config)
    async def wrapper():
        return await func(*args, **kwargs)

    return await wrapper()
