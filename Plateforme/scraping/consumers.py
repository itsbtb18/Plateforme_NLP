import json

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import ScrapingRun


class ScrapingStatusConsumer(AsyncWebsocketConsumer):
    """WebSocket stream for per-task scraping progress updates."""

    async def connect(self):
        self.task_uuid = self.scope["url_route"]["kwargs"]["task_uuid"]
        self.group_name = f"scraping_{self.task_uuid}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        # Send current status immediately on connect
        await self._send_current_status()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        # Client doesn't send messages, only receives.
        return

    async def status_update(self, event):
        # Called when Celery sends a group_send message.
        await self.send(
            text_data=json.dumps(
                {
                    "type": "status_update",
                    "task_uuid": self.task_uuid,
                    "status": event.get("status", "running"),
                    "progress": int(event.get("progress", 0)),
                    "total": int(event.get("total", 0)),
                    "items_scraped": int(event.get("items_scraped", 0)),
                    "items_failed": int(event.get("items_failed", 0)),
                    "current_source": event.get("current_source", ""),
                    "message": event.get("message", ""),
                    "timestamp": event.get("timestamp", ""),
                }
            )
        )

    async def _send_current_status(self):
        # Fetch current run status from DB and push immediately.
        try:
            run = await sync_to_async(ScrapingRun.objects.get)(pk=self.task_uuid)
            total_sources = getattr(run, "total_sources", 0) or 0
            progress = getattr(run, "progress", None)
            if progress is None:
                progress = 0
            items_scraped = getattr(run, "items_scraped", None)
            if items_scraped is None:
                items_scraped = int(run.items_created or 0)

            await self.send(
                text_data=json.dumps(
                    {
                        "type": "initial_status",
                        "status": run.status,
                        "progress": int(progress),
                        "total": int(total_sources),
                        "items_scraped": int(items_scraped),
                    }
                )
            )
        except ScrapingRun.DoesNotExist:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "error",
                        "message": "Task not found",
                    }
                )
            )
