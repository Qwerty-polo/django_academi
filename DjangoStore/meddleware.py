import hashlib
import time
from .rate_limits import CACHE_ERRORS, increment_counter, limited, unavailable


class GlobalRateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Forwarding headers are not trusted without a trusted proxy setup.
        identity = (f'user:{request.user.pk}' if request.user.is_authenticated
                    else f"ip:{request.META.get('REMOTE_ADDR', '')}")
        identity_hash = hashlib.sha256(identity.encode()).hexdigest()
        now = int(time.time())
        window = now // 60
        try:
            count = increment_counter(f'global-rate:{identity_hash}:{window}', timeout=60)
        except CACHE_ERRORS:
            return unavailable()
        if count > 30:
            return limited(60 - now % 60)
        return self.get_response(request)
