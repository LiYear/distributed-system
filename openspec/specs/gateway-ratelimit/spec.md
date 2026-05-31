## ADDED Requirements

### Requirement: Rate limiting on excessive requests
The system SHALL reject requests with status 429 when a single IP exceeds 10 requests within a 1-second sliding window.

#### Scenario: Normal requests pass through
- **WHEN** client sends ≤10 requests within 1 second from the same IP
- **THEN** all requests are processed normally without being rejected

#### Scenario: Excessive requests blocked
- **WHEN** client sends ≥11 requests within 1 second from the same IP
- **THEN** the 11th and subsequent requests return 429 with detail "请求过于频繁，请稍后再试"

#### Scenario: Rate limit resets after window passes
- **WHEN** client waits for the 1-second window to expire after being rate-limited
- **THEN** new requests are accepted normally again
