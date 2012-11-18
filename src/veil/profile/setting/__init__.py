import veil_component

with veil_component.init_component(__name__):
    from veil.environment import *
    from veil.environment.setting import *
    from veil.backend.database.new_postgresql_setting import postgresql_program
    from veil.backend.new_redis_setting import redis_program
    from veil.backend.new_queue_setting import queue_program
    from veil.backend.new_queue_setting import resweb_program
    from veil.backend.new_queue_setting import delayed_job_scheduler_program
    from veil.backend.new_queue_setting import periodic_job_scheduler_program
    from veil.backend.new_queue_setting import job_worker_program
