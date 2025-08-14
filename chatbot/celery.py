import os
from celery import Celery
from celery.signals import setup_logging

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatbot.settings.development')

app = Celery('chatbot')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

@setup_logging.connect
def config_loggers(loglevel, logfile, format, colorize, **kwargs):
    from django.conf import settings
    from logging.config import dictConfig
    dictConfig(settings.LOGGING)

# Task routing
app.conf.task_routes = {
    'tasks.document_tasks.*': {'queue': 'documents'},
    'tasks.agent_tasks.*': {'queue': 'agents'},
}

# Task rate limits
app.conf.task_annotations = {
    'tasks.document_tasks.process_large_file': {'rate_limit': '10/m'},
    'tasks.agent_tasks.run_agent_task': {'rate_limit': '30/m'},
}