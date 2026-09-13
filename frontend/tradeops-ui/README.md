# TradeOps Web Cockpit

React/TypeScript business/demo UI for TradeOps.

## Local development

Run the backend services on ports 8011/8012/8015, then:

```bash
npm install
npm run dev
```

Vite proxies `/api/market`, `/api/workflow` and `/api/agent` to the local APIs.

## Security

No API key or bearer token is committed or baked into the image. For the CRC static-auth demo, Agent/Reviewer bearer tokens are entered interactively and are held only in React memory. Refreshing the browser clears them.

## OpenShift

The image is built by `tradeops-ui` BuildConfig and served on port 8080. Nginx proxies API paths to internal services so MCP, databases, Kafka, Qdrant and Prometheus remain private.
