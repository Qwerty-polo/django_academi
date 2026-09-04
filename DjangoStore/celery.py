import os
from celery import Celery
from celery.schedules import crontab

# Встановлюємо налаштування Django за замовчуванням для Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'DjangoStore.settings')

app = Celery('DjangoStore')

# Celery буде автоматично брати налаштування з settings.py (усі, що починаються з CELERY_)
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматично шукати файли tasks.py у всіх твоїх додатках
app.autodiscover_tasks()


app.conf.beat_schedule = {
    'clear-sessions-every-night': {
        'task': 'courses.tasks.clear_old_sessions',
        # Запускати о 03:00 ночі кожного дня:
        'schedule': crontab(minute=0, hour=3),

    },
}