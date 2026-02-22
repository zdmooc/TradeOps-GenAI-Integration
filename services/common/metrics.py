import time
from fastapi import Request
from prometheus_client import Counter, Histogram

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "method", "path", "status"],
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["service", "method", "path"],
    buckets=(0.005,0.01,0.025,0.05,0.1,0.25,0.5,1,2,5,10),
)

def install(app, service_name: str):
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        elapsed = time.time() - start
        path = request.url.path
        http_requests_total.labels(service=service_name, method=request.method, path=path, status=str(response.status_code)).inc()
        http_request_duration_seconds.labels(service=service_name, method=request.method, path=path).observe(elapsed)
        return response
