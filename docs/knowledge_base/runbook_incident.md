# Incident Response Runbook

## High Latency on Order Execution
1. Check paper-oms service health: GET /health
2. Verify Kafka/Redpanda consumer lag via Prometheus metrics
3. Check PostgreSQL connection pool usage
4. If lag > 1000 messages: scale paper-oms replicas
5. Escalate to on-call if latency > 30 seconds

## Database Connection Failures
1. Verify PostgreSQL is running: docker compose ps postgres
2. Check connection count: SELECT count(*) FROM pg_stat_activity
3. If max connections reached: restart idle connections
4. Verify .env credentials match init.sql configuration

## Market Data Feed Issues
1. Check market-data service health endpoint
2. Verify Redpanda topic market.prices has recent messages
3. If no data: restart market-data service
4. Check external API rate limits if using real feeds
