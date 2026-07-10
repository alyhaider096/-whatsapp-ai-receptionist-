from arq.connections import RedisSettings

from app.core.config import get_settings
from app.worker.jobs import process_debounced_reply, process_whatsapp_webhook


class WorkerSettings:
    functions = [process_whatsapp_webhook, process_debounced_reply]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 10
    job_timeout = 60
