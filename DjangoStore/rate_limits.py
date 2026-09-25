"""Cache counters and controlled responses for request throttling."""
from functools import wraps
from django.core.cache import cache
from django.http import HttpResponse
from django_ratelimit.core import get_usage
from redis.exceptions import RedisError

CACHE_ERRORS = (RedisError, OSError, ValueError)


def increment_counter(key, timeout):
    # add/incr are atomic on Redis and LocMem. Retry a concurrent expiry once.
    for attempt in range(2):
        cache.add(key, 0, timeout=timeout)
        try:
            return cache.incr(key)
        except ValueError:
            if attempt:
                raise


def unavailable():
    response = HttpResponse('Request limiting is temporarily unavailable. Please retry.', status=503)
    response['Retry-After'] = '60'
    return response


def limited(seconds):
    response = HttpResponse('Too many requests.', status=429)
    response['Retry-After'] = str(max(1, seconds))
    return response


def ratelimit(*, key, rate, method):
    """Use django-ratelimit while failing closed on backend outages."""
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            try:
                usage = get_usage(request, fn=view, key=key, rate=rate,
                                  method=method, increment=True)
            except CACHE_ERRORS:
                return unavailable()
            if usage and usage['time_left'] < 0:
                return unavailable()
            if usage and usage['should_limit']:
                return limited(usage['time_left'])
            return view(request, *args, **kwargs)
        return wrapped
    return decorate
