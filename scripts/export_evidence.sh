# scripts/export_evidence.sh
#!/usr/bin/env bash
set -u

# Evidence folder (UTC timestamp)
TS="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
OUT="evidence/${TS}"

mkdir -p "${OUT}"/{sql,logs,system,http}
echo "${OUT}" > evidence/LATEST 2>/dev/null || true

# Helpers
now() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

log_cmd() {
  # Logs the command exactly as executed
  printf '[%s] ' "$(now)" | tee -a "${OUT}/commands.log" >/dev/null
  printf '%q ' "$@" | tee -a "${OUT}/commands.log" >/dev/null
  printf '\n' | tee -a "${OUT}/commands.log" >/dev/null
}

run() {
  # run <label> <cmd...>
  local label="$1"; shift
  log_cmd "$@"
  "$@" >"${OUT}/${label}.out" 2>"${OUT}/${label}.err" || {
    echo "[${label}] FAILED (see ${label}.err)" >> "${OUT}/run.log"
    return 0
  }
}

run_to() {
  # run_to <output_file_rel> <cmd...>
  local file="$1"; shift
  log_cmd "$@"
  "$@" >"${OUT}/${file}" 2>"${OUT}/${file}.err" || {
    echo "[${file}] FAILED (see ${file}.err)" >> "${OUT}/run.log"
    return 0
  }
}

sql_txt() {
  # sql_txt <name> <sql>
  local name="$1"; shift
  local q="$1"
  run_to "sql/${name}.txt" docker compose exec -T postgres \
    psql -U tradeops -d tradeops -P pager=off -c "${q}"
}

sql_csv() {
  # sql_csv <name> <sql_select_without_semicolon>
  local name="$1"; shift
  local sel="$1"
  local q="COPY (${sel}) TO STDOUT WITH CSV HEADER;"
  run_to "sql/${name}.csv" docker compose exec -T postgres \
    psql -U tradeops -d tradeops -P pager=off -c "${q}"
}

# ---------- System / Repo ----------
run system_docker_version        docker version
run system_docker_compose_version docker compose version
run system_docker_info           docker info
run system_compose_ps            docker compose ps
run system_compose_images        docker compose images
run system_compose_config_redacted bash -lc 'docker compose config | sed -E "s/(POSTGRES_PASSWORD:).*/\1 <redacted>/g; s/(KONG_PASSWORD:).*/\1 <redacted>/g"'

run system_git_status            git status
run system_git_rev               git rev-parse --short HEAD
run system_git_branch            git branch --show-current
run system_git_diff_stat         git diff --stat
run system_git_diff              git diff

# ---------- HTTP health via Gateway ----------
run_to "http/health_market.txt"   bash -lc 'curl -sS http://localhost:8000/market/health || true'
run_to "http/health_workflow.txt" bash -lc 'curl -sS http://localhost:8000/workflow/health || true'
run_to "http/health_genai.txt"    bash -lc 'curl -sS http://localhost:8000/genai/health || true'
run_to "http/health_rag_api.txt"   bash -lc 'curl -sS http://localhost:8014/health || true'
run_to "http/health_agent.txt"     bash -lc 'curl -sS http://localhost:8015/health || true'
run_to "http/health_mcp.txt"       bash -lc 'curl -sS http://localhost:8016/health || true'

# ---------- Logs (tail 250) ----------
for svc in postgres redpanda kong market-data workflow-api genai-api rag-api agent-controller mcp-server qdrant signal-engine risk-engine paper-oms notifier prometheus grafana tools; do
  run_to "logs/${svc}.log" docker compose logs --no-color --tail=250 "${svc}"
done

# ---------- DB schema / tables ----------
sql_txt "tables" '\dt'
sql_txt "schema_workflows" '\d+ workflows'
sql_txt "schema_orders" '\d+ orders'
sql_txt "schema_audit_logs" '\d+ audit_logs'

# ---------- DB evidence queries (TXT + CSV) ----------
sql_txt "audit_last_20" "select audit_id, kind, ref_id, correlation_id, hash, created_at from audit_logs order by audit_id desc limit 20;"
sql_csv "audit_last_200" "select audit_id, kind, ref_id, correlation_id, hash, created_at from audit_logs order by audit_id desc limit 200"

sql_txt "counts_by_kind" "select kind, count(*) as cnt, min(created_at) as first_seen, max(created_at) as last_seen from audit_logs group by kind order by cnt desc;"
sql_csv "counts_by_kind" "select kind, count(*) as cnt, min(created_at) as first_seen, max(created_at) as last_seen from audit_logs group by kind order by cnt desc"

sql_txt "workflows_extracted" "
select
  workflow_id,
  status,
  payload->>'symbol' as symbol,
  payload->>'side'   as side,
  (payload->>'qty')::numeric as qty,
  created_at
from workflows
order by created_at desc
limit 50;"
sql_csv "workflows_extracted" "
select
  workflow_id,
  status,
  payload->>'symbol' as symbol,
  payload->>'side'   as side,
  (payload->>'qty')::numeric as qty,
  created_at
from workflows
order by created_at desc
limit 500"

sql_txt "orders_last_50" "
select order_id, workflow_id, status, symbol, side, qty, fill_price, created_at
from orders
order by created_at desc
limit 50;"
sql_csv "orders_last_500" "
select order_id, workflow_id, status, symbol, side, qty, fill_price, created_at
from orders
order by created_at desc
limit 500"

sql_txt "chain_workflow_genai_filled" "
select
  w.workflow_id,
  w.status as workflow_status,
  o.order_id,
  o.status as order_status,
  o.symbol, o.side, o.qty, o.fill_price,
  ar.audit_id as genai_audit_id,
  ar.correlation_id as genai_corr,
  ar.created_at as genai_at,
  af.audit_id as filled_audit_id,
  af.correlation_id as filled_corr,
  af.created_at as filled_at
from workflows w
left join orders o
  on o.workflow_id = w.workflow_id
left join audit_logs ar
  on ar.kind='genai.review' and ar.ref_id = w.workflow_id::text
left join audit_logs af
  on af.kind='order.filled' and af.ref_id = o.order_id::text
order by w.created_at desc
limit 50;"
sql_csv "chain_workflow_genai_filled" "
select
  w.workflow_id,
  w.status as workflow_status,
  o.order_id,
  o.status as order_status,
  o.symbol, o.side, o.qty, o.fill_price,
  ar.audit_id as genai_audit_id,
  ar.correlation_id as genai_corr,
  ar.created_at as genai_at,
  af.audit_id as filled_audit_id,
  af.correlation_id as filled_corr,
  af.created_at as filled_at
from workflows w
left join orders o
  on o.workflow_id = w.workflow_id
left join audit_logs ar
  on ar.kind='genai.review' and ar.ref_id = w.workflow_id::text
left join audit_logs af
  on af.kind='order.filled' and af.ref_id = o.order_id::text
order by w.created_at desc
limit 500"

sql_txt "latency_review_to_filled" "
select
  w.workflow_id,
  round(extract(epoch from (af.created_at - ar.created_at))::numeric, 3) as seconds_review_to_filled
from workflows w
join orders o
  on o.workflow_id = w.workflow_id
join audit_logs ar
  on ar.kind='genai.review' and ar.ref_id = w.workflow_id::text
join audit_logs af
  on af.kind='order.filled' and af.ref_id = o.order_id::text
order by w.created_at desc
limit 100;"
sql_csv "latency_review_to_filled" "
select
  w.workflow_id,
  round(extract(epoch from (af.created_at - ar.created_at))::numeric, 3) as seconds_review_to_filled
from workflows w
join orders o
  on o.workflow_id = w.workflow_id
join audit_logs ar
  on ar.kind='genai.review' and ar.ref_id = w.workflow_id::text
join audit_logs af
  on af.kind='order.filled' and af.ref_id = o.order_id::text
order by w.created_at desc
limit 1000"

# ---------- Agent / MCP / RAG evidence ----------
sql_txt "workflows_agent_decisions" "
select
  workflow_id,
  status,
  decision,
  confidence_score,
  reviewer,
  payload->>'symbol' as symbol,
  payload->>'side'   as side,
  (payload->>'qty')::numeric as qty,
  created_at
from workflows
where decision is not null
order by created_at desc
limit 50;"
sql_csv "workflows_agent_decisions" "
select
  workflow_id,
  status,
  decision,
  confidence_score,
  reviewer,
  payload->>'symbol' as symbol,
  payload->>'side'   as side,
  (payload->>'qty')::numeric as qty,
  created_at
from workflows
where decision is not null
order by created_at desc
limit 500"

sql_txt "audit_agent_mcp_rag" "
select audit_id, kind, ref_id, correlation_id, hash, created_at
from audit_logs
where kind like 'agent.%' or kind like 'mcp.%' or kind like 'rag.%'
order by audit_id desc
limit 50;"
sql_csv "audit_agent_mcp_rag" "
select audit_id, kind, ref_id, correlation_id, hash, created_at
from audit_logs
where kind like 'agent.%' or kind like 'mcp.%' or kind like 'rag.%'
order by audit_id desc
limit 500"

# ---------- Human-readable summary ----------
cat > "${OUT}/SUMMARY.md" <<EOF
# Evidence bundle: ${TS}

## Quick links
- DB tables: sql/tables.txt
- Audit last 20: sql/audit_last_20.txt
- Counts by kind: sql/counts_by_kind.txt
- Chain (workflow ↔ genai ↔ filled): sql/chain_workflow_genai_filled.txt
- Latency review → filled: sql/latency_review_to_filled.txt
- Agent decisions: sql/workflows_agent_decisions.txt
- Agent/MCP/RAG audit: sql/audit_agent_mcp_rag.txt
- Compose status: system_compose_ps.out
- Gateway health: http/health_*.txt
- Service health: http/health_rag_api.txt, http/health_agent.txt, http/health_mcp.txt
- Logs: logs/*.log (includes rag-api, agent-controller, mcp-server, qdrant)

## Notes
- If you plan to share this folder externally, review \`system_compose_config_redacted.out\` and logs for any sensitive values.
EOF

echo "Evidence written to: ${OUT}"