## ADDED Requirements

### Requirement: Health check endpoint
The system SHALL respond to GET /health with status "ok".

#### Scenario: Health check succeeds
- **WHEN** client sends GET request to /health
- **THEN** response status is 200 and body contains `{"status": "ok"}`

### Requirement: Add goods
The system SHALL allow adding a new goods item with name, price, and stock fields.

#### Scenario: Add goods successfully
- **WHEN** client sends POST /goods/add with valid `{name, price, stock}`
- **THEN** response contains the created goods with an auto-generated id, matching name/price/stock, and the Redis cache for that goods id is deleted

#### Scenario: Add goods with invalid data
- **WHEN** client sends POST /goods/add with missing required fields or invalid values
- **THEN** response is a validation error with status 422

### Requirement: Get goods with Redis caching
The system SHALL retrieve goods information by id, using Redis cache with Cache-Aside pattern: check cache first, fall back to database on miss, and populate cache with random TTL jitter.

#### Scenario: Get existing goods from cache
- **WHEN** client sends GET /goods/{id} for an id that exists in Redis cache
- **THEN** response returns the goods data from cache without querying the database

#### Scenario: Get existing goods on cache miss
- **WHEN** client sends GET /goods/{id} for an id not in Redis cache but exists in database
- **THEN** system acquires a distributed lock, queries database, populates Redis cache with TTL between 300-360 seconds, and returns the goods data

#### Scenario: Get non-existent goods
- **WHEN** client sends GET /goods/{id} for an id not in database
- **THEN** system caches an empty marker with 60-second TTL and returns 404 "商品不存在"

### Requirement: Deduct goods stock
The system SHALL deduct stock from a goods item by a given quantity, and delete the Redis cache entry after update.

#### Scenario: Deduct stock successfully
- **WHEN** client sends PUT /goods/stock/{id}?num=N with sufficient stock
- **THEN** stock is reduced by N in database, Redis cache for that goods id is deleted, and response returns `{"code": 200, "msg": "扣库存成功"}`

#### Scenario: Deduct stock with insufficient inventory
- **WHEN** client sends PUT /goods/stock/{id}?num=N with N exceeding available stock
- **THEN** response returns 400 "库存不足" and stock remains unchanged

### Requirement: Gateway routing to goods-service
The system SHALL route requests with path prefix /goods from the gateway to goods-service via Nacos service discovery.

#### Scenario: Gateway proxies goods API
- **WHEN** client sends any /goods/* request to gateway (port 8080)
- **THEN** request is forwarded to goods-service (port 8002) and response is returned correctly
