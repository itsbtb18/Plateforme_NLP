import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db.models import Q

from .models import ScrapingRun

logger = logging.getLogger(__name__)


class ScrapingStatusConsumer(AsyncWebsocketConsumer):
    """WebSocket stream for per-run scraping events."""

    async def connect(self):
        self.task_uuid = self.scope["url_route"]["kwargs"]["task_uuid"]
        self.group_name = f"scraping_{self.task_uuid}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self._send_current_status()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        return

    async def scraping_event(self, event):
        """Unified handler for all scraping websocket event types."""
        await self.send(text_data=json.dumps(event))

    async def status_update(self, event):
        """Backward-compatible handler for legacy status_update payloads."""
        await self.send(text_data=json.dumps(event))

    async def _send_current_status(self):
        """Send current run state to newly connected clients."""
        try:
            run = await database_sync_to_async(
                lambda: ScrapingRun.objects.filter(
                    Q(task_id=self.task_uuid) | Q(id=self.task_uuid)
                ).first()
            )()

            if run is None:
                return

            progress_current = int(
                getattr(run, "progress_current", getattr(run, "progress", 0)) or 0
            )
            progress_total = int(
                getattr(run, "progress_total", getattr(run, "total_sources", 0)) or 0
            )
            current_step = str(getattr(run, "current_step", "") or "")
            current_message = str(getattr(run, "current_message", "") or "")
            current_source = str(getattr(run, "current_source", "") or "")
            current_item = str(
                getattr(run, "current_item", getattr(run, "current_source", "")) or ""
            )
            items_created = int(
                getattr(run, "items_created", getattr(run, "items_scraped", 0)) or 0
            )
            items_failed = int(
                getattr(run, "items_failed", getattr(run, "items_skipped", 0)) or 0
            )
            percent = (
                int((progress_current / progress_total) * 100)
                if progress_total > 0
                else 0
            )
            message = current_message or current_step

            await self.send(
                text_data=json.dumps(
                    {
                        "type": "scraping_event",
                        "event_type": "initial_status",
                        "run_id": str(getattr(run, "id", self.task_uuid)),
                        "task_uuid": str(self.task_uuid),
                        "status": run.status,
                        "step": current_step,
                        "current": progress_current,
                        "total": progress_total,
                        "percent": percent,
                        "message": message,
                        "items_created": int(items_created),
                        "progress_current": progress_current,
                        "progress_total": progress_total,
                        "progress": progress_current,
                        "current_step": current_step,
                        "current_message": message,
                        "current_source": current_source,
                        "current_item": current_item,
                        "items_scraped": int(items_created),
                        "items_failed": int(items_failed),
                    }
                )
            )
        except Exception as exc:
            logger.warning("Could not send initial status: %s", exc)
