import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.cache import cache
from unittest.mock import patch
from .models import Profile



# 1. ТЕСТУВАННЯ РЕЄСТРАЦІЇ ТА RATELIMIT
@pytest.mark.django_db
def test_registration_view(client):
    cache.clear()  # Чистимо лічильник перед реєстрацією
    url = reverse('reg')

    # 1. GET запит (просто відкрили сторінку)
    response = client.get(url)
    assert response.status_code == 200
    assert 'form' in response.context

    # 2. POST запит (Успішна реєстрація)
    form_data = {
        'username': 'newuser123',
        'email': 'new@user.com',
        'password1': 'StrongPassword123!',
        'password2': 'StrongPassword123!'
    }
    response = client.post(url, data=form_data)
    assert response.status_code == 302  # Редирект на головну ('home')
    assert User.objects.filter(username='newuser123').exists()

    # Чистимо кеш ще раз, щоб нас не заблокувало за 2 запити на секунду!
    cache.clear()

    # 3. POST запит (Помилка: паролі не співпадають)
    bad_data = form_data.copy()
    bad_data['password2'] = 'WrongPassword!'
    response = client.post(url, data=bad_data)
    assert response.status_code == 200  # Залишаємось на сторінці з помилками


# 2. ТЕСТУВАННЯ ПРОФІЛЮ ТА ОНОВЛЕННЯ ДАНИХ
@pytest.mark.django_db
def test_profile_view_and_forms(client):
    user = User.objects.create_user(username='testprofile', email='old@test.com', password='pw')
    client.force_login(user)
    url = reverse('profile')

    # 1. GET запит
    response = client.get(url)
    assert response.status_code == 200

    # 2. POST запит (Успішне оновлення імені та згоди на розсилку)
    update_data = {
        'username': 'updated_name',
        'email': 'new@test.com',
        'gender': 'male',
        'email_consent': True
    }
    response = client.post(url, data=update_data)
    assert response.status_code == 302  # Успіх - редирект на 'profile'

    # Оновлюємо об'єкт юзера з бази даних, щоб перевірити зміни
    user.refresh_from_db()
    assert user.username == 'updated_name'
    assert user.profile.gender == 'male'

    # 3. POST запит (Помилка: порожнє ім'я користувача)
    bad_update_data = update_data.copy()
    bad_update_data['username'] = ''
    response = client.post(url, data=bad_update_data)
    assert response.status_code == 200  # Залишаємось на сторінці



# 3. ТЕСТУВАННЯ ЛОГАУТУ (ВИХОДУ)
@pytest.mark.django_db
def test_custom_logout(client):
    user = User.objects.create_user(username='logouter', password='pw')
    client.force_login(user)

    url = reverse('exit')
    response = client.post(url)
    assert response.status_code == 200  # Відмалювалася сторінка exit.html



    assert "_auth_user_id" not in client.session


# 4. ТЕСТУВАННЯ МОДЕЛЕЙ (Сигнали, __str__, is_vip)
@pytest.mark.django_db
def test_profile_model_methods():
    # Коли створюється юзер, сигнал автоматично створює Profile (тестуємо signals.py!)
    user = User.objects.create_user(username='vip_tester', password='pw')

    # Перевірка методу __str__
    assert str(user.profile) == 'Профіль користувача vip_tester'

    # Перевірка property is_vip
    assert user.profile.is_vip is False  # За замовчуванням 'free'

    # Робимо акаунт VIP і перевіряємо ще раз
    user.profile.account_type = 'full'
    user.profile.save()
    assert user.profile.is_vip is True


# 5. ТЕСТУВАННЯ ЗБЕРЕЖЕННЯ ЗОБРАЖЕННЯ (Resize та Exceptions)
# Знову використовуємо patch, щоб підмінити бібліотеку Image
@pytest.mark.django_db
@patch('users.models.Image.open')
def test_profile_image_resizing(mock_image_open):
    user = User.objects.create_user(username='picuser', password='pw')

    # Сценарій 1: Імітуємо величезну картинку (щоб виконався if image.height > 256)
    mock_img = mock_image_open.return_value
    mock_img.height = 500
    mock_img.width = 500

    user.profile.save()  # Це викличе try блок з resize
    mock_img.thumbnail.assert_called_with((256, 256))
    mock_img.save.assert_called()

    # Сценарій 2: Імітуємо збій/відсутність файлу (щоб виконався except Exception: pass)
    mock_image_open.side_effect = Exception("Fake Image Error")
    user.profile.save()  # Python проігнорує помилку, бо в нас стоїть pass