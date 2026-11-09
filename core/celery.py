import os
from celery import Celery

# Set default Django settings module for 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')

# Read config from Django settings with CELERY_ prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover task modules from all registered Django app packages.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    """
    Diagnostic Celery task printing the current task execution request context.

    :param self: Task instance bound to this execution.
    :return: Formatted request representation string.
    """
    print(f'Request: {self.request!r}')
    return f'Request: {self.request!r}'
