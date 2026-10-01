import logging

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@require_GET
def health(request):
    """Liveness/readiness probe used by Docker and load balancers."""
    checks = {"database": _check_database(), "cache": _check_cache()}
    healthy = all(checks.values())
    return JsonResponse(
        {"status": "ok" if healthy else "degraded", "checks": checks},
        status=200 if healthy else 503,
    )


def _check_database() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception:
        logger.exception("Database health check failed")
        return False


def _check_cache() -> bool:
    try:
        cache.set("healthcheck", "ok", timeout=5)
        return cache.get("healthcheck") == "ok"
    except Exception:
        logger.exception("Cache health check failed")
        return False
