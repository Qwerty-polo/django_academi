from celery import shared_task
from django.core.mail import send_mail
from django.contrib.auth.models import User
from django.core.management import call_command

@shared_task
def clear_old_sessions():
    """Видаляє всі прострочені сесії користувачів з бази даних"""
    call_command('clearsessions')
    return "Старі сесії успішно видалено!"


@shared_task
def send_new_course_email(course_title):
    # 1. Дістаємо email-адреси всіх користувачів
    users = User.objects.exclude(email='').values_list('email', flat=True)
    user_emails = list(users)

    if not user_emails:
        return "Немає користувачів з email-ами."

    # 2. Формуємо лист
    subject = f'🚀 New course on the platform: {course_title}!'
    message = f'Hello! We are just add a new course: "{course_title}". Заходь і навчайся!'
    from_email = 'admin@academystore.com'

    # 3. Відправляємо (в нашому випадку - виведеться в консоль)
    send_mail(
        subject,
        message,
        from_email,
        user_emails,
        fail_silently=False,
    )

    return f"Send {len(user_emails)} Emails"