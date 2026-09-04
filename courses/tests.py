import time

from django.core import mail
from .tasks import clear_old_sessions, send_new_course_email

import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch

from DjangoStore import settings
from .models import Course, Lesson, Comment



# 1. ТЕСТУВАННЯ ПРОСТИХ СТОРІНОК
@pytest.mark.django_db
def test_home_and_tariffs_pages(client):
    # Тестуємо головну сторінку
    response = client.get(reverse('home'))
    assert response.status_code == 200
    assert response.context['title'] == 'Home Page'

    # Тестуємо сторінку тарифів
    response = client.get(reverse('tarrifs'))
    assert response.status_code == 200



# 2. ТЕСТУВАННЯ REDIS ЛІЧИЛЬНИКА (CourseDetail)
@pytest.mark.django_db
def test_course_detail_redis_views(client):
    cache.clear()  #Очищаємо Redis перед стартом!
    course = Course.objects.create(slug='redis-course', title='Redis', desc='Desc')
    url = reverse('course-detail', kwargs={'slug': course.slug})

    # Перший захід на сторінку (перегляд = 1)
    response = client.get(url)
    assert response.status_code == 200
    assert response.context['views_count'] == 1

    # Другий захід (має стати 2)
    response = client.get(url)
    assert response.context['views_count'] == 2



# 3. ТЕСТУВАННЯ УРОКІВ (Доступ та Відео)
@pytest.mark.django_db
def test_lesson_detail_video_parsing_and_access(client):
    course = Course.objects.create(slug='paid-course', title='Paid', desc='Desc', is_free=False)
    lesson1 = Lesson.objects.create(course=course, slug='l1', title='L1', video='https://youtube.com/watch?v=12345',
                                    number=1)
    lesson2 = Lesson.objects.create(course=course, slug='l2', title='L2', video='https://youtu.be/67890', number=2)

    user = User.objects.create_user(username='vip_user', password='pw')

    url1 = reverse('lesson-detail', kwargs={'slug': course.slug, 'lesson_slug': lesson1.slug})
    response = client.get(url1)
    assert response.context['has_access'] is False
    assert response.context['video_code'] == '12345'

    # ФІКС: Змінюємо тип акаунту, щоб @property is_vip повернуло True
    user.profile.account_type = 'full'
    user.profile.save()
    client.force_login(user)

    response = client.get(url1)
    assert response.context['has_access'] is True

    url2 = reverse('lesson-detail', kwargs={'slug': course.slug, 'lesson_slug': lesson2.slug})
    response = client.get(url2)
    assert response.context['video_code'] == '67890'

    url_404 = reverse('lesson-detail', kwargs={'slug': course.slug, 'lesson_slug': 'fake'})
    response = client.get(url_404)
    assert response.status_code == 404

# 4. ТЕСТУВАННЯ КОМЕНТАРІВ (Логін, Антиспам, Форма)
@pytest.mark.django_db
def test_lesson_comments_logic(client):

    course = Course.objects.create(slug='free-course', title='Free', desc='Desc', is_free=True)
    lesson = Lesson.objects.create(course=course, slug='l1', title='L1', video='123', number=1)
    url = reverse('lesson-detail', kwargs={'slug': course.slug, 'lesson_slug': lesson.slug})

    response = client.post(url, data={'text': 'Hello'})
    assert response.status_code == 302
    assert '/user/' in response.url

    user = User.objects.create_user(username='commenter', password='pw')
    client.force_login(user)

    response = client.post(url, data={'text': 'Мій перший комент!'})
    time.sleep(0.6)  # Даємо секунді передихнути
    assert response.status_code == 302
    assert Comment.objects.count() == 1

    response = client.post(url, data={'text': 'Другий комент!'})
    assert response.status_code == 302
    assert Comment.objects.count() == 1

    cache.clear()

    user2 = User.objects.create_user(username='commenter2', password='pw')
    client.force_login(user2)

    response = client.post(url, data={'text': ''})
    assert response.status_code == 200
    assert 'comment_form' in response.context


# 5. ТЕСТУВАННЯ СТВОРЕННЯ КУРСУ (Права та Celery)
# Використовуємо patch, щоб імітувати виклик Celery без реального Redis
@patch('courses.views.send_new_course_email.delay')
@pytest.mark.django_db
def test_add_course_permissions_and_creation(mock_celery_delay, client):
    url = reverse('add-course')

    # 1. Звичайний залогінений юзер -> відмова (handle_no_permission)
    normie = User.objects.create_user(username='normie', password='pw')
    client.force_login(normie)
    response = client.get(url)
    assert response.status_code == 302

    # 2. Суперюзер -> доступ дозволено
    admin = User.objects.create_superuser(username='admin', password='pw')
    client.force_login(admin)
    response = client.get(url)
    assert response.status_code == 200

    # 3. Юзер-автор створює курс
    author = User.objects.create_user(username='author', password='pw')
    author.profile.is_author = True
    author.profile.save()
    client.force_login(author)

    form_data = {
        'slug': 'new-course',
        'title': 'Курс по Celery',
        'desc': 'Опис...',
    }

    response = client.post(url, data=form_data)



# 6. (__str__ та get_absolute_url)
@pytest.mark.django_db
def test_models_methods():
    # Створюємо тестові дані
    user = User.objects.create_user(username='tester', password='pw')
    course = Course.objects.create(slug='test-course', title='Тестовий курс', desc='Опис')
    lesson = Lesson.objects.create(course=course, slug='test-lesson', title='Вступ', video='123', number=1)
    comment = Comment.objects.create(user=user, lesson=lesson, text='Круто!')

    # Перевіряємо __str__
    assert str(course) == 'Тестовий курс'
    assert str(lesson) == 'Тестовий курс - Вступ'
    assert str(comment) == 'Comment by tester on Вступ'

    # Перевіряємо get_absolute_url
    assert course.get_absolute_url() == reverse('course-detail', kwargs={'slug': course.slug})
    assert lesson.get_absolute_url() == reverse('lesson-detail',
                                                kwargs={'slug': course.slug, 'lesson_slug': lesson.slug})


# 7. ТЕСТУВАННЯ CELERY ТАСОК
@pytest.mark.django_db
def test_celery_tasks():
    # 1. Тестуємо видалення сесій (перевіряємо, чи повертає правильний текст)
    result_sessions = clear_old_sessions()
    assert result_sessions == "Старі сесії успішно видалено!"

    # 2. Тестуємо розсилку листів КОЛИ НЕМАЄ КОРИСТУВАЧІВ з email
    result_no_emails = send_new_course_email('Курс по Celery')
    assert result_no_emails == "Немає користувачів з email-ами."

    # 3. Тестуємо розсилку КОЛИ Є КОРИСТУВАЧІ з email
    User.objects.create_user(username='user1', email='user1@test.com', password='pw')
    User.objects.create_user(username='user2', email='user2@test.com', password='pw')

    result_with_emails = send_new_course_email('Курс по Docker')
    assert result_with_emails == "Send 2 Emails"

    # Джанго під час тестів розумний: він не відправляє реальні листи,
    # а складає їх у віртуальну "поштову скриньку" mail.outbox. Перевіримо її!
    assert len(mail.outbox) == 1
    assert mail.outbox[0].subject == '🚀 New course on the platform: Курс по Docker!'
    assert list(mail.outbox[0].to) == ['user1@test.com', 'user2@test.com']