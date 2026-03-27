"""
Central schedule configuration for scraping periodic tasks.

This is the runtime source used by the sync management command.
"""

SCRAPING_SCHEDULES = [
    {
        "name": "update-adaptive-schedules",
        "task": "scraping.tasks.update_adaptive_schedules",
        "minute": "0",
        "hour": "3",
        "day_of_week": "*",
        "day_of_month": "*",
        "month_of_year": "*",
        "args": "[]",
        "enabled": True,
    },
]
