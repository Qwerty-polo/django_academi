"""Opt-in tests for the disposable docker-compose.integration.yml services.

The outage test stops/restarts only the explicitly named integration Redis service.
Never enable these tests against a shared database or cache.
"""
import os
from pathlib import Path
import subprocess
import time
import uuid

import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse
from redis import Redis

from DjangoStore.celery import app
from DjangoStore.rate_limits import increment_counter, ratelimit
from courses.models import Course
from courses.tasks import send_new_course_email
from courses.views import AddCourseView

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(os.environ.get('RUN_SERVICE_INTEGRATION') != '1',
                       reason='Opt-in test requires disposable PostgreSQL/Redis services.'),
]


def test_real_redis_counter_ttl_and_endpoint_expiry():
    assert settings.CACHES['default']['BACKEND'].endswith('RedisCache')
    redis = Redis.from_url(settings.REDIS_URL)
    key = 'integration-ttl-' + uuid.uuid4().hex
    assert increment_counter(key, timeout=2) == 1
    ttl_before = redis.pttl(cache.make_key(key))
    assert 0 < ttl_before <= 2000
    time.sleep(0.1)
    assert increment_counter(key, timeout=2) == 2
    assert 0 < redis.pttl(cache.make_key(key)) < ttl_before
    deadline = time.monotonic() + 4
    while cache.get(key) is not None and time.monotonic() < deadline:
        time.sleep(0.05)
    assert cache.get(key) is None
    assert increment_counter(key, timeout=2) == 1

    @ratelimit(key='ip', rate='2/s', method='POST')
    def endpoint(request):
        return HttpResponse('ok')
    request = RequestFactory().post('/', REMOTE_ADDR='192.0.2.50')
    request.user = AnonymousUser()
    # Freeze no clocks: allow crossing a second boundary while exhausting a window.
    for _ in range(6):
        response = endpoint(request)
        if response.status_code == 429:
            break
    assert response.status_code == 429
    time.sleep(int(response['Retry-After']) + 0.1)
    assert endpoint(request).status_code == 200


def test_real_celery_broker_publishes_task(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = False
    assert app.conf.task_always_eager is False
    queue_name = 'integration-' + uuid.uuid4().hex
    # Consume the message directly so no application worker or email is needed.
    with app.connection_for_write() as connection:
        with connection.SimpleQueue(queue_name) as queue:
            try:
                result = send_new_course_email.apply_async(
                    args=['Integration transport check'], queue=queue_name,
                    connection=connection, retry=False,
                )
                message = queue.get(block=True, timeout=5)
                assert message.headers['id'] == result.id
                assert message.headers['task'] == 'courses.tasks.send_new_course_email'
                assert message.payload[0] == ['Integration transport check']
                message.ack()
            finally:
                queue.clear()
                queue.queue.delete()


def test_real_redis_outage_and_broker_failure(client, course_data, settings,
                                               django_capture_on_commit_callbacks, caplog):
    project = os.environ.get('INTEGRATION_COMPOSE_PROJECT', '')
    assert project.startswith('academy-integration-'), 'Refusing to stop a non-integration service'
    compose = Path(__file__).resolve().parents[1] / 'docker-compose.integration.yml'
    command = ['docker', 'compose', '-f', str(compose), '-p', project]
    container = subprocess.check_output([*command, 'ps', '-q', 'redis'], text=True).strip()
    assert container, 'The dedicated integration Redis service must already be running'
    label = subprocess.check_output(['docker', 'inspect', '--format',
        '{{index .Config.Labels "com.docker.compose.project"}}', container], text=True).strip()
    assert label == project
    assert settings.REDIS_URL == 'redis://127.0.0.1:16379/1'
    assert app.conf.broker_url == 'redis://127.0.0.1:16379/0'

    author = User.objects.create_user('outage-author', 'author@example.com', 'pw')
    author.profile.is_author = True
    author.profile.save()
    settings.CELERY_TASK_ALWAYS_EAGER = False
    assert app.conf.task_always_eager is False
    try:
        subprocess.run([*command, 'stop', '-t', '2', 'redis'], check=True)
        response = client.get('/')
        assert response.status_code == 503
        assert response['Retry-After'] == '60'

        @ratelimit(key='ip', rate='2/s', method='POST')
        def endpoint(request):
            pytest.fail('An unavailable throttle must not allow the protected operation')
        request = RequestFactory().post('/', REMOTE_ADDR='192.0.2.50')
        request.user = AnonymousUser()
        assert endpoint(request).status_code == 503

        # Exercise the view's post-commit publishing independently of global throttling.
        request = RequestFactory().post(reverse('add-course'), course_data())
        request.user = author
        with django_capture_on_commit_callbacks(execute=True):
            response = AddCourseView.as_view()(request)
        assert response.status_code == 302
        assert Course.objects.filter(slug='created', author=author).exists()
        assert 'Error calling' in caplog.text
    finally:
        subprocess.run([*command, 'up', '-d', '--wait', 'redis'], check=True)
        cache.close()
    assert client.get('/').status_code == 200
