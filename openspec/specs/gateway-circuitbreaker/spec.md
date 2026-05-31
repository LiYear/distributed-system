## ADDED Requirements

### Requirement: Circuit breaker opens on consecutive failures
The system SHALL open the circuit breaker for a downstream service port after 5 consecutive failures, returning 503 immediately for 30 seconds.

#### Scenario: Normal routing before failures
- **WHEN** downstream goods-service is healthy and client sends requests via gateway
- **THEN** requests are forwarded normally and responses are returned successfully

#### Scenario: Circuit breaker opens after 5 consecutive failures
- **WHEN** downstream goods-service is stopped and the gateway encounters 5 consecutive connection failures to its port (8002)
- **THEN** the circuit breaker state changes to "open" and the 6th request returns 503 "服务 goods-service 暂时不可用"

#### Scenario: Circuit breaker half-open and recovery after timeout
- **WHEN** 30 seconds have passed since the circuit breaker opened for port 8002
- **THEN** the circuit breaker transitions to "half_open" and if the downstream service has recovered, the next successful request resets the breaker to "closed"

### Requirement: Circuit breaker metrics observable
The system SHALL expose circuit breaker state and failure counts via GET /metrics/gateway.

#### Scenario: Metrics show circuit breaker status
- **WHEN** client sends GET /metrics/gateway
- **THEN** response includes circuit_breakers object with per-port state and failure count
