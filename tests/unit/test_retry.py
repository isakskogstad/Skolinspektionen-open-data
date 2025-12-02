"""Tests for retry module."""

import time

import httpx
import pytest

from src.services.retry import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    MaxRetriesExceededError,
    RetryConfig,
    calculate_delay,
    is_retryable_exception,
    with_retry,
)


class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_default_config(self):
        """Test default retry configuration."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.backoff_factor == 2.0
        assert config.jitter

    def test_custom_config(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            max_attempts=5,
            initial_delay=0.5,
            max_delay=30.0,
            backoff_factor=3.0,
            jitter=False,
        )
        assert config.max_attempts == 5
        assert config.initial_delay == 0.5
        assert config.max_delay == 30.0
        assert config.backoff_factor == 3.0
        assert not config.jitter


class TestCalculateDelay:
    """Tests for calculate_delay function."""

    def test_initial_delay(self):
        """Test first attempt uses initial delay."""
        config = RetryConfig(initial_delay=1.0, backoff_factor=2.0, jitter=False)
        delay = calculate_delay(0, config)
        assert delay == 1.0

    def test_exponential_increase(self):
        """Test delay increases exponentially."""
        config = RetryConfig(initial_delay=1.0, backoff_factor=2.0, jitter=False)
        delay1 = calculate_delay(1, config)
        delay2 = calculate_delay(2, config)
        assert delay1 == 2.0
        assert delay2 == 4.0

    def test_max_delay_cap(self):
        """Test delay is capped at max_delay."""
        config = RetryConfig(initial_delay=1.0, backoff_factor=10.0, max_delay=5.0, jitter=False)
        delay = calculate_delay(5, config)
        assert delay == 5.0

    def test_jitter_variation(self):
        """Test jitter adds variation."""
        config = RetryConfig(initial_delay=1.0, backoff_factor=2.0, jitter=True)
        delays = [calculate_delay(1, config) for _ in range(10)]
        # With jitter, we should get some variation
        assert len(set(delays)) > 1


class TestIsRetryableException:
    """Tests for is_retryable_exception function."""

    def test_timeout_is_retryable(self):
        """Test timeout exception is retryable."""
        exc = httpx.TimeoutException("timeout")
        assert is_retryable_exception(exc)

    def test_connect_error_is_retryable(self):
        """Test connect error is retryable."""
        exc = httpx.ConnectError("connection failed")
        assert is_retryable_exception(exc)

    def test_value_error_not_retryable(self):
        """Test ValueError is not retryable."""
        exc = ValueError("invalid")
        assert not is_retryable_exception(exc)


class TestWithRetry:
    """Tests for with_retry decorator."""

    @pytest.mark.asyncio
    async def test_success_no_retry(self):
        """Test that successful calls don't retry."""
        call_count = 0

        @with_retry(RetryConfig(max_attempts=3))
        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        """Test that timeout exceptions trigger retries."""
        call_count = 0

        @with_retry(RetryConfig(max_attempts=3, initial_delay=0.01, jitter=False))
        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("timeout")
            return "success"

        result = await failing_func()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test MaxRetriesExceededError is raised after max attempts."""
        call_count = 0

        @with_retry(RetryConfig(max_attempts=3, initial_delay=0.01, jitter=False))
        async def always_failing():
            nonlocal call_count
            call_count += 1
            raise httpx.TimeoutException("persistent timeout")

        with pytest.raises(MaxRetriesExceededError) as exc_info:
            await always_failing()

        assert call_count == 3
        assert exc_info.value.last_exception is not None

    @pytest.mark.asyncio
    async def test_non_retryable_exception_not_retried(self):
        """Test non-retryable exceptions are raised immediately."""
        call_count = 0

        @with_retry(RetryConfig(max_attempts=3, initial_delay=0.01))
        async def raises_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError):
            await raises_value_error()

        assert call_count == 1  # Only called once


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig."""

    def test_default_config(self):
        """Test default circuit breaker configuration."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.success_threshold == 2
        assert config.timeout == 60.0


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    @pytest.fixture
    def breaker(self) -> CircuitBreaker:
        """Create a circuit breaker for testing."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=1,
            timeout=0.1,  # Short for testing
        )
        return CircuitBreaker(config)

    def test_initial_state(self, breaker: CircuitBreaker):
        """Test initial state is closed."""
        assert breaker.state == CircuitState.CLOSED
        assert breaker.can_execute()

    def test_failures_open_circuit(self, breaker: CircuitBreaker):
        """Test that failures open the circuit."""
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        assert not breaker.can_execute()

    def test_success_resets_failures(self, breaker: CircuitBreaker):
        """Test that success resets failure count."""
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_success()

        # After success, should need 3 more failures to open
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED

    def test_half_open_after_timeout(self, breaker: CircuitBreaker):
        """Test circuit goes half-open after recovery timeout."""
        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)

        # Should allow one request (half-open)
        assert breaker.can_execute()
        assert breaker.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes(self, breaker: CircuitBreaker):
        """Test success in half-open state closes circuit."""
        # Open circuit
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()

        # Wait and move to half-open
        time.sleep(0.15)
        breaker.can_execute()

        # Success should close
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self, breaker: CircuitBreaker):
        """Test failure in half-open state reopens circuit."""
        # Open circuit
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()

        # Wait and move to half-open
        time.sleep(0.15)
        breaker.can_execute()

        # Failure should reopen
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN


class TestCircuitBreakerWithRetry:
    """Tests for circuit breaker integration with retry."""

    @pytest.mark.asyncio
    async def test_circuit_prevents_calls(self):
        """Test that open circuit prevents function calls."""
        config = CircuitBreakerConfig(failure_threshold=2, timeout=10.0)
        breaker = CircuitBreaker(config)
        call_count = 0

        async def guarded_func():
            nonlocal call_count
            if not breaker.can_execute():
                raise Exception("Circuit open")
            call_count += 1
            breaker.record_failure()
            raise ValueError("always fails")

        # First two calls should execute
        with pytest.raises(ValueError):
            await guarded_func()
        with pytest.raises(ValueError):
            await guarded_func()

        # Circuit should be open, call should not execute
        with pytest.raises(Exception, match="Circuit open"):
            await guarded_func()

        assert call_count == 2  # Only 2 actual calls
