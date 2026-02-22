# Démo (pas à pas)

1) Démarrer
```bash
make up
```

2) Publier un prix (MarketData -> Kafka)
```bash
curl -X POST http://localhost:8011/publish/AAPL
```

3) Créer une demande de trade
```bash
curl -X POST http://localhost:8012/trade-requests \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","side":"BUY","qty":250,"reason":"Breakout"}'
```

4) Le GenAI consomme `workflow.requested` et produit une revue (mock)
   - vérifier `docker compose logs genai-api -f`

5) Approuver
```bash
curl -X POST http://localhost:8012/trade-requests/<ID>/approve \
  -H "Content-Type: application/json" \
  -d '{"approver":"risk-user","comment":"OK"}'
```

6) Vérifier orders & audit
- audit: `GET http://localhost:8012/audit`
- logs notifier: `docker compose logs notifier -f`
