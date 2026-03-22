"""
Central schedule configuration for scraping periodic tasks.

This is the runtime source used by the sync management command.
"""

SCRAPING_SCHEDULES = [
    {
        "name": "Auto-scrape News Daily",
        "task": "scraping.tasks.run_scraper_task",
        "minute": "0",
        "hour": "4",
        "day_of_week": "*",
        "day_of_month": "*",
        "month_of_year": "*",
        "args": '["news"]',
        "enabled": True,
    },
    {
        "name": "Auto-scrape Events Weekly",
        "task": "scraping.tasks.run_scraper_task",
        "minute": "0",
        "hour": "2",
        "day_of_week": "1",
        "day_of_month": "*",
        "month_of_year": "*",
        "args": '["events"]',
        "enabled": True,
    },
    {
        "name": "Auto-scrape Tools Weekly",
        "task": "scraping.tasks.run_scraper_task",
        "minute": "0",
        "hour": "3",
        "day_of_week": "1",
        "day_of_month": "*",
        "month_of_year": "*",
        "args": '["tools"]',
        "enabled": True,
    },
    {
        "name": "Auto-scrape Courses Monthly",
        "task": "scraping.tasks.run_scraper_task",
        "minute": "0",
        "hour": "5",
        "day_of_week": "*",
        "day_of_month": "1",
        "month_of_year": "*",
        "args": '["courses"]',
        "enabled": True,
    },
    {
        "name": "Auto-scrape Institutions Monthly",
        "task": "scraping.tasks.run_scraper_task",
        "minute": "0",
        "hour": "6",
        "day_of_week": "*",
        "day_of_month": "1",
        "month_of_year": "*",
        "args": '["institutions"]',
        "enabled": True,
    },
]
