from celery import Celery
from src.core.config import settings


celery_app = Celery(
    'tasks',
    broker=settings.REDIS_URL,
    backend='db+' + settings.DATABASE_URL,
    include=['src.tasks.notifications', 'src.tasks.reminders']
)

celery_app.conf.update(
    result_expires=3600,
)


celery_app.conf.beat_schedule = {
    'send_daily_slot_reminders': {
        'task': 'src.tasks.reminders.send_daily_slot_reminders',
        'schedule': 86400.0, # Раз в день (в секундах)
    },
    'check_no_show_baristas_and_notify': {
        'task': 'src.tasks.reminders.check_no_show_baristas_and_notify',
        'schedule': 600.0,  # Каждые 10 минут (в секундах)
    },
}


if __name__ == "__main__":
    celery_app.worker_main()
