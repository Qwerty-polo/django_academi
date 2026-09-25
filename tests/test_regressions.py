from datetime import timedelta
from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit
import re

import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.core import mail
from django.core.cache import cache
from django.db import transaction
from django.http import HttpResponse
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import timezone
from redis.exceptions import ConnectionError as RedisConnectionError

from courses.models import Course, Lesson, Comment
from courses.tasks import send_new_course_email
from DjangoStore.meddleware import GlobalRateLimitMiddleware

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return User.objects.create_user('learner', 'learner@example.com', 'Old-Password-739!')


@pytest.fixture
def lesson():
    course = Course.objects.create(slug='course', title='Course', desc='Course description')
    return Lesson.objects.create(course=course, slug='intro', title='Intro', number=1,
                                 desc='Private lesson text', video='https://youtu.be/abcdefghijk')




class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.nested = False
        self.methods = []
    def handle_starttag(self, tag, attrs):
        if tag == 'form':
            self.nested |= self.depth > 0
            self.depth += 1
            self.methods.append(dict(attrs).get('method', 'get').lower())
    def handle_endtag(self, tag):
        if tag == 'form':
            self.depth -= 1


def test_password_reset_end_to_end(user):
    client = Client(enforce_csrf_checks=True)
    start = client.get(reverse('pass-reset'))
    parser = FormParser()
    parser.feed(start.content.decode())
    assert not parser.nested
    assert parser.methods == ['post']
    assert client.post(reverse('pass-reset'), {'email': user.email}).status_code == 403
    response = client.post(reverse('pass-reset'), {'email': user.email,
                          'csrfmiddlewaretoken': client.cookies['csrftoken'].value})
    assert response.url == reverse('password_reset_done')
    assert len(mail.outbox) == 1 and mail.outbox[0].to == [user.email]
    reset_path = urlsplit(re.search(r'https?://[^\s]+', mail.outbox[0].body).group()).path
    page = client.get(reset_path, follow=True)
    assert page.context['validlink'] is True
    parser = FormParser()
    parser.feed(page.content.decode())
    assert not parser.nested and parser.methods == ['post']
    target = page.redirect_chain[-1][0]
    bad = client.post(target, {'new_password1': 'New-Password-842!', 'new_password2': 'mismatch',
                             'csrfmiddlewaretoken': client.cookies['csrftoken'].value})
    assert bad.status_code == 200 and bad.context['form'].errors
    done = client.post(target, {'new_password1': 'New-Password-842!', 'new_password2': 'New-Password-842!',
                               'csrfmiddlewaretoken': client.cookies['csrftoken'].value}, follow=True)
    assert done.redirect_chain[-1][0] == reverse('password_reset_complete')
    assert done.context['login_url'] == reverse('user')
    assert '<form' not in done.content.decode()
    user.refresh_from_db()
    assert user.check_password('New-Password-842!')
    assert not client.login(username=user.username, password='Old-Password-739!')
    assert client.login(username=user.username, password='New-Password-842!')
    assert Client().get(reset_path, follow=True).context['validlink'] is False


def test_reset_unknown_email_and_invalid_token(client, user):
    assert client.post(reverse('pass-reset'), {'email': 'unknown@example.com'}).status_code == 302
    assert len(mail.outbox) == 0
    page = client.get(reverse('password_reset_confirm', args=['bad', 'bad']))
    assert page.context['validlink'] is False
    assert 'name="new_password1"' not in page.content.decode()


def test_logout_requires_post_and_csrf(user):
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    assert client.get(reverse('exit')).status_code == 405
    assert '_auth_user_id' in client.session
    assert client.post(reverse('exit')).status_code == 403
    client.get(reverse('profile'))
    response = client.post(reverse('exit'), {'csrfmiddlewaretoken': client.cookies['csrftoken'].value})
    assert response.status_code == 200
    assert '_auth_user_id' not in client.session


def test_profile_login_target_and_ownership(client, user):
    response = client.get(reverse('profile'))
    assert urlsplit(response.url).path == reverse('user')
    other = User.objects.create_user('other', 'other@example.com', 'pw')
    client.force_login(user)
    page = client.get(reverse('profile'))
    assert 'name="email_consent"' in page.content.decode()
    assert 'name="gender"' in page.content.decode()
    response = client.post(reverse('profile'), {'username': 'edited', 'email': 'edited@example.com',
        'gender': 'female', 'user': other.pk, 'is_author': True, 'is_superuser': True, 'account_type': 'full'})
    assert response.status_code == 302
    user.refresh_from_db(); other.refresh_from_db()
    assert user.username == 'edited' and other.username == 'other'
    assert not user.is_superuser and not user.profile.is_author and not user.profile.is_vip
    assert user.profile.email_consent is False


@pytest.mark.parametrize('authenticated', [False, True])
def test_locked_lesson_hides_comments_and_blocks_posts(client, user, lesson, authenticated):
    lesson.course.is_free = False
    lesson.course.save()
    Comment.objects.create(user=user, lesson=lesson, text='Restricted discussion')
    if authenticated:
        client.force_login(user)
    page = client.get(lesson.get_absolute_url())
    assert 'Restricted discussion' not in page.content.decode()
    assert 'Private lesson text' not in page.content.decode()
    assert 'name="text"' not in page.content.decode()
    response = client.post(lesson.get_absolute_url(), {'text': 'Bypass'})
    assert response.status_code == (403 if authenticated else 302)
    assert Comment.objects.count() == 1


def test_comment_identity_cooldown_pagination_and_course_scope(client, user, lesson):
    other = User.objects.create_user('other', password='pw')
    other_course = Course.objects.create(slug='other', title='Other', desc='Other')
    other_lesson = Lesson.objects.create(course=other_course, slug='intro', title='Other intro', number=1, video='abc')
    client.force_login(user)
    result = client.post(lesson.get_absolute_url(), {'text': 'Owned', 'user': other.pk, 'lesson': other_lesson.pk})
    assert result.status_code == 302
    comment = Comment.objects.get()
    assert comment.user == user and comment.lesson == lesson
    cache.clear()
    assert client.post(other_lesson.get_absolute_url(), {'text': 'Too soon'}).status_code == 302
    assert Comment.objects.count() == 1
    Comment.objects.filter(pk=comment.pk).update(created_at=timezone.now()-timedelta(seconds=61))
    cache.clear()
    assert client.post(other_lesson.get_absolute_url(), {'text': 'Allowed'}).status_code == 302
    assert Comment.objects.count() == 2
    Comment.objects.bulk_create([Comment(user=other, lesson=lesson, text=str(i)) for i in range(5)])
    assert len(client.get(lesson.get_absolute_url()).context['comments']) == 3
    assert client.get(lesson.get_absolute_url()+'?page=invalid').context['page_obj'].number == 1
    assert client.get(lesson.get_absolute_url()+'?page=999').context['page_obj'].number == 2
    assert client.get(reverse('lesson-detail', args=['absent', lesson.slug])).status_code == 404


@pytest.mark.parametrize('url,expected', [
    ('https://www.youtube.com/watch?v=abcdefghijk&t=20', 'abcdefghijk'),
    ('https://youtu.be/abcdefghijk?t=20', 'abcdefghijk'),
])
def test_video_query_parameters(client, lesson, url, expected):
    lesson.video = url; lesson.save()
    assert client.get(lesson.get_absolute_url()).context['video_code'] == expected


def test_course_permissions_and_commit_dispatch(client, user, course_data, django_capture_on_commit_callbacks):
    data = course_data()
    assert client.post(reverse('add-course'), data).status_code == 302
    client.force_login(user)
    assert client.post(reverse('add-course'), course_data()).status_code in (302, 403)
    assert not Course.objects.exists()
    user.profile.is_author = True; user.profile.save()
    with patch('courses.views.send_new_course_email.delay') as dispatch:
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            response = client.post(reverse('add-course'), {**course_data(), 'author': 999, 'is_free': False})
            assert response.status_code == 302
            assert Course.objects.get(slug='created').author == user
            assert Course.objects.get(slug='created').is_free
            dispatch.assert_not_called()
        assert len(callbacks) == 1
        dispatch.assert_called_once_with('Created')


def test_rolled_back_course_never_announces(client, user, course_data, django_capture_on_commit_callbacks):
    user.profile.is_author = True; user.profile.save()
    client.force_login(user)
    with patch('courses.views.send_new_course_email.delay') as dispatch:
        with django_capture_on_commit_callbacks(execute=True):
            with pytest.raises(RuntimeError):
                with transaction.atomic():
                    assert client.post(reverse('add-course'), course_data()).status_code == 302
                    raise RuntimeError('rollback')
        dispatch.assert_not_called()
    assert not Course.objects.exists()


def test_announcements_respect_consent_and_recipient_privacy(user):
    opted_out = User.objects.create_user('optout', 'no@example.com', 'pw')
    opted_out.profile.email_consent = False; opted_out.profile.save()
    User.objects.create_user('disabled', 'disabled@example.com', 'pw', is_active=False)
    User.objects.create_user('second', 'second@example.com', 'pw')
    User.objects.create_user('duplicate', user.email, 'pw')
    assert send_new_course_email('Course') == 'Send 2 Emails'
    assert len(mail.outbox) == 2
    assert {tuple(m.to) for m in mail.outbox} == {(user.email,), ('second@example.com',)}


def middleware_request(user_id=None):
    request = RequestFactory().get('/', REMOTE_ADDR='127.0.0.1')
    request.user = AnonymousUser() if user_id is None else SimpleNamespace(is_authenticated=True, pk=user_id)
    return request


def test_global_throttle_is_per_user_and_returns_429():
    middleware = GlobalRateLimitMiddleware(lambda request: HttpResponse('ok'))
    for _ in range(30):
        assert middleware(middleware_request(1)).status_code == 200
    response = middleware(middleware_request(1))
    assert response.status_code == 429 and int(response['Retry-After']) > 0
    assert middleware(middleware_request(2)).status_code == 200


def test_global_throttle_does_not_extend_window():
    middleware = GlobalRateLimitMiddleware(lambda request: HttpResponse('ok'))
    with patch('time.time', return_value=1200):
        assert middleware(middleware_request()).status_code == 200
    with patch('time.time', return_value=1259):
        for _ in range(29):
            assert middleware(middleware_request()).status_code == 200
    with patch('time.time', return_value=1261):
        assert middleware(middleware_request()).status_code == 200


def test_cache_outage_is_controlled_and_does_not_run_view():
    from unittest.mock import Mock
    view = Mock(return_value=HttpResponse('ok'))
    with patch.object(cache, 'get', side_effect=RedisConnectionError), patch.object(cache, 'add', side_effect=RedisConnectionError):
        response = GlobalRateLimitMiddleware(view)(middleware_request())
    assert response.status_code == 503
    view.assert_not_called()



def test_password_reset_expired_token_and_safe_login_redirect(client, user, settings):
    from datetime import datetime
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode
    settings.PASSWORD_RESET_TIMEOUT = 60
    with patch.object(default_token_generator, '_now', return_value=datetime(2020, 1, 1)):
        token = default_token_generator.make_token(user)
    response = client.get(reverse('password_reset_confirm', args=[urlsafe_base64_encode(force_bytes(user.pk)), token]))
    assert response.context['validlink'] is False
    response = client.post(reverse('user'), {'username': user.username, 'password': 'Old-Password-739!',
                                           'next': 'https://untrusted.example/'})
    assert response.url == reverse('home')


def test_registration_cannot_set_privileges_and_requires_csrf():
    client = Client(enforce_csrf_checks=True)
    client.get(reverse('reg'))
    data = {'username': 'registered', 'email': 'registered@example.com',
            'password1': 'Register-Strong-739!', 'password2': 'Register-Strong-739!',
            'is_superuser': True, 'is_staff': True, 'is_author': True, 'account_type': 'full'}
    assert client.post(reverse('reg'), data).status_code == 403
    data['csrfmiddlewaretoken'] = client.cookies['csrftoken'].value
    assert client.post(reverse('reg'), data).status_code == 302
    registered = User.objects.get(username='registered')
    assert not registered.is_staff and not registered.is_superuser
    assert not registered.profile.is_author and not registered.profile.is_vip


def test_lesson_access_order_and_admin_permissions(client, user, lesson):
    second = Lesson.objects.create(course=lesson.course, slug='second', title='Second', number=2, video='abc')
    page = client.get(lesson.course.get_absolute_url())
    assert list(page.context['lessons']) == [lesson, second]
    lesson.course.is_free = False; lesson.course.save()
    user.profile.account_type = 'full'; user.profile.save()
    client.force_login(user)
    page = client.get(lesson.course.get_absolute_url())
    assert list(page.context['lessons']) == [lesson, second]
    assert client.post(lesson.get_absolute_url(), {'text': 'Full access'}).status_code == 302
    assert Comment.objects.get().user == user
    assert client.get('/admin/courses/course/add/').status_code == 302
    user.is_staff = True; user.save()
    assert client.get('/admin/courses/course/add/').status_code == 403


def test_course_save_failure_and_broker_failure(client, user, course_data, django_capture_on_commit_callbacks, caplog):
    user.profile.is_author = True; user.profile.save()
    client.force_login(user)
    with patch('courses.views.send_new_course_email.delay') as dispatch:
        with patch.object(Course, 'save', side_effect=RuntimeError('save failed')):
            with pytest.raises(RuntimeError, match='save failed'):
                client.post(reverse('add-course'), course_data())
        dispatch.assert_not_called()
    with patch('courses.views.send_new_course_email.delay', side_effect=ConnectionError('broker down')):
        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(reverse('add-course'), course_data())
    assert response.status_code == 302 and Course.objects.filter(slug='created').exists()
    assert 'broker down' in caplog.text


def test_counter_parallel_updates_and_course_metric_outage(client, lesson):
    from concurrent.futures import ThreadPoolExecutor
    from DjangoStore.rate_limits import increment_counter
    with ThreadPoolExecutor(max_workers=8) as pool:
        values = list(pool.map(lambda _: increment_counter('parallel-counter', 60), range(100)))
    assert sorted(values) == list(range(1, 101))
    with patch('courses.views.increment_counter', side_effect=RedisConnectionError):
        response = client.get(lesson.course.get_absolute_url())
    assert response.status_code == 200 and response.context['views_count'] is None


def test_endpoint_throttle_identity_and_outage():
    from DjangoStore.rate_limits import ratelimit
    @ratelimit(key='user_or_ip', rate='2/s', method='POST')
    def view(request):
        return HttpResponse('ok')
    request = middleware_request(1); request.method = 'POST'
    with patch('time.time', return_value=1200):
        assert [view(request).status_code for _ in range(3)] == [200, 200, 429]
        other = middleware_request(2); other.method = 'POST'
        assert view(other).status_code == 200
    with patch('DjangoStore.rate_limits.get_usage', side_effect=RedisConnectionError):
        assert view(request).status_code == 503
    with patch('DjangoStore.rate_limits.get_usage', return_value={'time_left': -1, 'should_limit': True}):
        assert view(request).status_code == 503


def test_forwarded_header_does_not_bypass_global_throttle():
    middleware = GlobalRateLimitMiddleware(lambda request: HttpResponse('ok'))
    for i in range(30):
        request = middleware_request()
        request.META['HTTP_X_FORWARDED_FOR'] = f'192.0.2.{i}'
        assert middleware(request).status_code == 200
    assert middleware(middleware_request()).status_code == 429


@pytest.mark.django_db(transaction=True)
def test_concurrent_comment_cooldown_postgresql(user, lesson):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from django.db import connection, close_old_connections
    if connection.vendor != 'postgresql':
        pytest.skip('Requires PostgreSQL row locks; SQLite does not implement select_for_update.')
    clients = [Client(), Client()]
    for client in clients:
        client.force_login(user)
    gate = Barrier(2)
    def post(client):
        close_old_connections()
        try:
            gate.wait(timeout=10)
            return client.post(lesson.get_absolute_url(), {'text': 'Concurrent'}).status_code
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(post, clients)) == [302, 302]
    assert Comment.objects.filter(user=user).count() == 1



def test_eager_notification_runs_after_saved_course(client, user, course_data, django_capture_on_commit_callbacks):
    user.profile.is_author = True; user.profile.save()
    client.force_login(user)
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = client.post(reverse('add-course'), course_data())
        assert response.status_code == 302
        assert Course.objects.filter(slug='created').exists()
        assert len(mail.outbox) == 0
    assert len(callbacks) == 1
    assert len(mail.outbox) == 1 and mail.outbox[0].to == [user.email]
