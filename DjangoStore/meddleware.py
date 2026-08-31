from django.core.cache import cache
from django.http import HttpResponseForbidden


class GlobalRateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # Цей метод викликається один раз при старті сервера

    def __call__(self, request):
        # Цей метод викликається при КОЖНОМУ запиті юзера

        # 1. Отримуємо IP юзера
        ip = request.META.get('REMOTE_ADDR')

        # Створюємо унікальний ключ для Кешу, наприклад: "rate_limit_127.0.0.1"
        cache_key = f"rate_limit_{ip}"

        # 2. Дістаємо кількість запитів (якщо IP ще не заходив, за замовчуванням буде 0)
        requests_count = cache.get(cache_key, 0)

        # 3. Перевіряємо ліміт (ставимо 100 запитів)
        if requests_count >= 100:
            return HttpResponseForbidden("Too many requests.")

        # 4. Якщо все ок — збільшуємо лічильник на +1.
        # timeout=60 означає, що через 60 секунд цей лічильник автоматично видалиться з бази.
        cache.set(cache_key, requests_count + 1, timeout=60)

        # 5. Передаємо запит далі (в інші middleware або у в'юху)
        response = self.get_response(request)
        return response
