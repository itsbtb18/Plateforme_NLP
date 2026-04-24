import httpx
from typing import Any

from app.ai.cache import get_ai_cache
from app.ai.chunking import StructureAwareChunker
from app.ai.document_intelligence import DocumentIntelligenceService
from app.ai.model_router import get_model_router
from app.ai.quality import get_quality_service
from app.ai.rag import get_rag_service
from app.ai.storage import get_object_storage
from app.config import get_settings


class AIPipelineService:
    def __init__(self) -> None:
        self.doc_intel = DocumentIntelligenceService()
        self.chunker = StructureAwareChunker()
        self.cache = get_ai_cache()
        self.router = get_model_router()
        self.rag = get_rag_service()
        self.quality = get_quality_service()
        self.storage = get_object_storage()
        self.settings = get_settings()

    async def _call_ts_service(self, endpoint: str, payload: dict) -> dict:
        url = f"{self.settings.TS_SERVICE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {"X-TS-API-KEY": self.settings.TS_SERVICE_API_KEY}
        timeout_seconds = max(60.0, float(getattr(self.settings, "TS_SERVICE_TIMEOUT_SECONDS", 420.0)))
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            try:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    raise RuntimeError("AI provider rate limit reached (via TS service)")
                raise RuntimeError(f"TS service error: {exc.response.text}")
            except Exception as exc:
                raise RuntimeError(f"Failed to reach TS service: {exc}")

    @staticmethod
    def _low_confidence(text: str) -> bool:
        if not text or len(text.strip()) < 20:
            return True
        lowered = text.lower()
        markers = [
            "wasn't able to complete",
            "je n'ai pas pu",
            "أعتذر",
            "unable to",
            "cannot",
            "error",
        ]
        return any(marker in lowered for marker in markers)

    async def _run_with_fallback(
        self,
        *,
        chain: list,
        call,
    ) -> tuple[str, str]:
        last_error: Exception | None = None
        for provider, decision in chain:
            try:
                output = await call(provider)
                if self._low_confidence(output):
                    raise RuntimeError(f"Low-confidence output from {provider.name}")
                return output, decision.provider_name
            except Exception as exc:
                last_error = exc
                continue
        raise RuntimeError(f"All providers failed: {last_error}")

    async def run_translation(self, *, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        document = payload["document"]
        source_language = payload.get("source_language")
        target_language = payload["target_language"]
        glossary = payload.get("glossary") or {}
        domain = payload.get("domain")

        cir = self.doc_intel.parse_document(
            file_uri=document.get("file_uri"),
            raw_text=document.get("raw_text"),
            filename=document.get("filename"),
            mime_type=document.get("mime_type"),
            source_language=source_language,
        )
        chunks = self.chunker.build_semantic_chunks(cir)

        chain = await self.router.choose_chain(
            task="translation",
            language=target_language,
            domain=domain,
            input_chars=sum(len(c.text) for c in chunks),
            sample_text="\n".join(c.text[:400] for c in chunks[:2]),
        )

        chosen_provider_name_holder = {"name": chain[0][1].provider_name}

        async def translate_chunk(chunk_text: str) -> str:
            cache_key = self.cache.stable_hash(
                {
                    "task": "translation",
                    "text": chunk_text,
                    "source_language": cir.source_language,
                    "target_language": target_language,
                    "glossary": glossary,
                }
            )
            cached = self.cache.get_json("translation", cache_key)
            if cached:
                return str(cached["text"])

            try:
                # Primary: Funnel through global scheduler
                ts_resp = await self._call_ts_service(
                    "/translate",
                    {
                        "text": chunk_text,
                        "source_language": cir.source_language,
                        "target_language": target_language,
                        "user_id": job_id,
                    }
                )
                translated = ts_resp["output"]
                provider_name = ts_resp["provider_used"]
            except Exception:
                # Fallback to local (bypasses scheduler, use sparingly)
                translated, provider_name = await self._run_with_fallback(
                    chain=chain,
                    call=lambda provider: provider.translate(
                        text=chunk_text,
                        source_language=cir.source_language,
                        target_language=target_language,
                        glossary=glossary,
                        preserve_named_entities=payload.get("preserve_named_entities", True),
                    ),
                )
            
            chosen_provider_name_holder["name"] = provider_name
            self.cache.set_json("translation", cache_key, {"text": translated}, ttl=60 * 60 * 24 * 7)
            return translated

        translated_chunks = []
        for chunk in chunks:
            translated_chunks.append(await translate_chunk(chunk.text))
        translated_text = "\n\n".join(translated_chunks)
        quality = self.quality.translation_quality(
            source_text="\n".join(b.text for b in cir.structural_blocks),
            translated_text=translated_text,
            glossary=glossary,
        )

        output_uri = self.storage.write_text_result(job_id=job_id, suffix="translation", content=translated_text)
        return {
            "provider": chosen_provider_name_holder["name"],
            "source_language": cir.source_language,
            "target_language": target_language,
            "output_text": translated_text,
            "output_uri": output_uri,
            "quality": quality,
            "metadata": {
                "chunk_count": len(chunks),
                "strategy": "sequential-structure-aware",
                "estimated_cost_usd": sum(d.estimated_cost_usd for _, d in chain),
                "estimated_latency_ms": min(d.estimated_latency_ms for _, d in chain),
            },
        }

    async def run_summarization(self, *, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        document = payload["document"]
        style = payload.get("style", "executive")
        source_language = payload.get("source_language")
        domain = payload.get("domain")

        cir = self.doc_intel.parse_document(
            file_uri=document.get("file_uri"),
            raw_text=document.get("raw_text"),
            filename=document.get("filename"),
            mime_type=document.get("mime_type"),
            source_language=source_language,
        )
        chunks = self.chunker.build_semantic_chunks(cir)

        chunk_dicts = [
            {"chunk_id": c.chunk_id, "text": c.text, "section": c.section}
            for c in chunks
        ]
        self.rag.upsert_chunks(job_id, chunk_dicts)

        chain = await self.router.choose_chain(
            task="summarization",
            language=cir.source_language,
            domain=domain,
            input_chars=sum(len(c.text) for c in chunks),
            sample_text="\n".join(c.text[:400] for c in chunks[:2]),
        )
        chosen_provider_name = chain[0][1].provider_name

        total_tokens = sum(c.token_count for c in chunks)
        if total_tokens <= 1200:
            strategy = "single-pass"
            try:
                ts_resp = await self._call_ts_service(
                    "/summarize",
                    {
                        "text": "\n\n".join(c.text for c in chunks),
                        "language": cir.source_language,
                        "style": style,
                        "max_words": payload.get("max_words"),
                        "user_id": job_id,
                    }
                )
                summary = ts_resp["output"]
                chosen_provider_name = ts_resp["provider_used"]
            except Exception:
                summary, chosen_provider_name = await self._run_with_fallback(
                    chain=chain,
                    call=lambda provider: provider.summarize(
                        text="\n\n".join(c.text for c in chunks),
                        language=cir.source_language,
                        style=style,
                        max_words=payload.get("max_words"),
                        context_snippets=self.rag.retrieve(" ".join(c.text[:120] for c in chunks[:2]), limit=4),
                    ),
                )
        elif total_tokens <= 7000:
            strategy = "map-reduce"
            mapped = []
            for c in chunks:
                try:
                    ts_resp = await self._call_ts_service(
                        "/summarize",
                        {
                            "text": c.text,
                            "language": cir.source_language,
                            "style": "brief",
                            "max_words": 220,
                            "user_id": job_id,
                        }
                    )
                    mapped_piece = ts_resp["output"]
                    chosen_provider_name = ts_resp["provider_used"]
                except Exception:
                    mapped_piece, chosen_provider_name = await self._run_with_fallback(
                        chain=chain,
                        call=lambda provider, chunk=c: provider.summarize(
                            text=chunk.text,
                            language=cir.source_language,
                            style="brief",
                            max_words=220,
                            context_snippets=None,
                        ),
                    )
                mapped.append(mapped_piece)
            
            try:
                ts_resp = await self._call_ts_service(
                    "/summarize",
                    {
                        "text": "\n\n".join(mapped),
                        "language": cir.source_language,
                        "style": style,
                        "max_words": payload.get("max_words"),
                        "user_id": job_id,
                    }
                )
                summary = ts_resp["output"]
                chosen_provider_name = ts_resp["provider_used"]
            except Exception:
                summary, chosen_provider_name = await self._run_with_fallback(
                    chain=chain,
                    call=lambda provider: provider.summarize(
                        text="\n\n".join(mapped),
                        language=cir.source_language,
                        style=style,
                        max_words=payload.get("max_words"),
                        context_snippets=self.rag.retrieve(" ".join(mapped[:3]), limit=5),
                    ),
                )
        else:
            strategy = "hierarchical"
            section_buckets: dict[str, list[str]] = {}
            for c in chunks:
                section = c.section or "general"
                section_buckets.setdefault(section, []).append(c.text)

            section_summaries: list[str] = []
            for section, texts in section_buckets.items():
                section_summary, chosen_provider_name = await self._run_with_fallback(
                    chain=chain,
                    call=lambda provider, section_texts=texts: provider.summarize(
                        text="\n".join(section_texts),
                        language=cir.source_language,
                        style="brief",
                        max_words=300,
                        context_snippets=None,
                    ),
                )
                section_summaries.append(f"{section}: {section_summary}")

            summary, chosen_provider_name = await self._run_with_fallback(
                chain=chain,
                call=lambda provider: provider.summarize(
                    text="\n\n".join(section_summaries),
                    language=cir.source_language,
                    style=style,
                    max_words=payload.get("max_words"),
                    context_snippets=self.rag.retrieve(" ".join(section_summaries[:2]), limit=6),
                ),
            )

        source_text = "\n".join(b.text for b in cir.structural_blocks)
        quality = self.quality.summarization_quality(source_text, summary)

        # Faithfulness verification and optional self-heal.
        hallucination_risk = self.quality.hallucination_risk(source_text, summary)
        quality["hallucination_risk"] = hallucination_risk
        if quality.get("faithfulness", 0.0) < 0.55 or hallucination_risk > 0.55:
            regenerated, chosen_provider_name = await self._run_with_fallback(
                chain=chain,
                call=lambda provider: provider.summarize(
                    text=source_text,
                    language=cir.source_language,
                    style="detailed",
                    max_words=payload.get("max_words") or 450,
                    context_snippets=self.rag.retrieve(source_text[:300], limit=8),
                ),
            )
            regen_quality = self.quality.summarization_quality(source_text, regenerated)
            if regen_quality.get("faithfulness", 0.0) > quality.get("faithfulness", 0.0):
                summary = regenerated
                quality = regen_quality
            else:
                quality["flagged_for_review"] = 1.0

        output_uri = self.storage.write_text_result(job_id=job_id, suffix="summary", content=summary)
        return {
            "provider": chosen_provider_name,
            "source_language": cir.source_language,
            "target_language": cir.source_language,
            "output_text": summary,
            "output_uri": output_uri,
            "quality": quality,
            "metadata": {
                "chunk_count": len(chunks),
                "strategy": strategy,
                "estimated_cost_usd": sum(d.estimated_cost_usd for _, d in chain),
                "estimated_latency_ms": min(d.estimated_latency_ms for _, d in chain),
            },
        }


_pipeline: AIPipelineService | None = None


def get_ai_pipeline_service() -> AIPipelineService:
    global _pipeline
    if _pipeline is None:
        _pipeline = AIPipelineService()
    return _pipeline
