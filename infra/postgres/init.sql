CREATE TABLE IF NOT EXISTS workflows (
  workflow_id UUID PRIMARY KEY,
  status TEXT NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS orders (
  order_id UUID PRIMARY KEY,
  workflow_id UUID NOT NULL,
  status TEXT NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  qty NUMERIC NOT NULL,
  fill_price NUMERIC,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_logs (
  audit_id BIGSERIAL PRIMARY KEY,
  kind TEXT NOT NULL,
  ref_id TEXT NOT NULL,
  data JSONB NOT NULL,
  hash TEXT NOT NULL,
  correlation_id UUID NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_ref ON audit_logs(ref_id);
CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status);
