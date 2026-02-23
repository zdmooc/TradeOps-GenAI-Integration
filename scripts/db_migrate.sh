#!/usr/bin/env bash
set -euo pipefail

docker compose exec -T postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
ALTER TABLE workflows ADD COLUMN IF NOT EXISTS confidence_score numeric;
ALTER TABLE workflows ADD COLUMN IF NOT EXISTS decision text;
ALTER TABLE workflows ADD COLUMN IF NOT EXISTS reviewer text;
"'
echo "DB migration OK"
