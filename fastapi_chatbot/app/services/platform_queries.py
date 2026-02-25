"""
Platform queries service — structured PostgreSQL queries against Django tables.

Provides resource lookup, metadata queries, author lookup, event search,
and navigation assistance by querying the Django platform's actual tables
(resources_*, events_*, institutions_*, projects_*, QA_*, accounts_*).
"""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class PlatformQueryService:
    """Query the Django platform's PostgreSQL tables for structured metadata."""

    # ------------------------------------------------------------------
    # Resource search (courses, documents, tools, corpora)
    # ------------------------------------------------------------------

    async def search_resources(
        self,
        db: AsyncSession,
        keyword: Optional[str] = None,
        resource_type: Optional[str] = None,
        language: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        """Search across all resource types (courses, documents, tools, corpora)."""
        results: List[Dict] = []

        if not resource_type or resource_type in ("course", "courses"):
            results.extend(await self._search_courses(db, keyword, language, limit))
        if not resource_type or resource_type in ("document", "documents", "article", "thesis", "memoir"):
            results.extend(await self._search_documents(db, keyword, resource_type, language, limit))
        if not resource_type or resource_type in ("tool", "tools", "nlptool"):
            results.extend(await self._search_tools(db, keyword, language, limit))
        if not resource_type or resource_type in ("corpus", "corpora"):
            results.extend(await self._search_corpora(db, keyword, language, limit))

        results.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return results[:limit]

    async def _search_courses(
        self, db: AsyncSession, keyword: Optional[str],
        language: Optional[str], limit: int,
    ) -> List[Dict]:
        conditions = ["approval_status = 'approved'"]
        params: Dict = {"lim": limit}

        if keyword:
            conditions.append(
                "(title ILIKE :kw OR title_ar ILIKE :kw OR title_en ILIKE :kw "
                "OR description ILIKE :kw)"
            )
            params["kw"] = f"%{keyword}%"
        if language:
            conditions.append("language = :lang")
            params["lang"] = language

        where = " AND ".join(conditions)
        query = text(f"""
            SELECT id::text, title, title_ar, title_en, description,
                   field, academic_level, academic_year,
                   language, creation_date, views_count
            FROM resources_course
            WHERE {where}
            ORDER BY creation_date DESC
            LIMIT :lim
        """)
        rows = (await db.execute(query, params)).mappings().all()
        return [
            {
                "id": r["id"], "type": "course",
                "title": r["title_en"] or r["title_ar"] or r["title"],
                "description": (r["description"] or "")[:300],
                "field": r["field"], "level": r["academic_level"],
                "academic_year": r["academic_year"],
                "language": r["language"],
                "created_at": str(r["creation_date"]) if r["creation_date"] else None,
                "views": r["views_count"],
            }
            for r in rows
        ]

    async def _search_documents(
        self, db: AsyncSession, keyword: Optional[str],
        doc_type: Optional[str], language: Optional[str], limit: int,
    ) -> List[Dict]:
        conditions = ["approval_status = 'approved'"]
        params: Dict = {"lim": limit}

        if keyword:
            conditions.append(
                "(title ILIKE :kw OR title_ar ILIKE :kw OR title_en ILIKE :kw "
                "OR description ILIKE :kw)"
            )
            params["kw"] = f"%{keyword}%"
        if doc_type in ("article", "thesis", "memoir"):
            conditions.append("document_type = :dtype")
            params["dtype"] = doc_type
        if language:
            conditions.append("language = :lang")
            params["lang"] = language

        where = " AND ".join(conditions)
        query = text(f"""
            SELECT id::text, title, title_ar, title_en, description,
                   document_type, file_format, language,
                   creation_date, views_count
            FROM resources_document
            WHERE {where}
            ORDER BY creation_date DESC
            LIMIT :lim
        """)
        rows = (await db.execute(query, params)).mappings().all()
        return [
            {
                "id": r["id"], "type": "document",
                "title": r["title_en"] or r["title_ar"] or r["title"],
                "description": (r["description"] or "")[:300],
                "document_type": r["document_type"],
                "format": r["file_format"],
                "language": r["language"],
                "created_at": str(r["creation_date"]) if r["creation_date"] else None,
                "views": r["views_count"],
            }
            for r in rows
        ]

    async def _search_tools(
        self, db: AsyncSession, keyword: Optional[str],
        language: Optional[str], limit: int,
    ) -> List[Dict]:
        conditions = ["approval_status = 'approved'"]
        params: Dict = {"lim": limit}

        if keyword:
            conditions.append(
                "(title ILIKE :kw OR title_ar ILIKE :kw OR title_en ILIKE :kw "
                "OR description ILIKE :kw)"
            )
            params["kw"] = f"%{keyword}%"
        if language:
            conditions.append("language = :lang")
            params["lang"] = language

        where = " AND ".join(conditions)
        query = text(f"""
            SELECT id::text, title, title_ar, title_en, description,
                   tool_type, version, supported_languages,
                   language, creation_date, views_count
            FROM resources_nlptool
            WHERE {where}
            ORDER BY creation_date DESC
            LIMIT :lim
        """)
        rows = (await db.execute(query, params)).mappings().all()
        return [
            {
                "id": r["id"], "type": "tool",
                "title": r["title_en"] or r["title_ar"] or r["title"],
                "description": (r["description"] or "")[:300],
                "tool_type": r["tool_type"],
                "version": r["version"],
                "supported_languages": r["supported_languages"],
                "language": r["language"],
                "created_at": str(r["creation_date"]) if r["creation_date"] else None,
                "views": r["views_count"],
            }
            for r in rows
        ]

    async def _search_corpora(
        self, db: AsyncSession, keyword: Optional[str],
        language: Optional[str], limit: int,
    ) -> List[Dict]:
        conditions = ["approval_status = 'approved'"]
        params: Dict = {"lim": limit}

        if keyword:
            conditions.append(
                "(title ILIKE :kw OR title_ar ILIKE :kw OR title_en ILIKE :kw "
                "OR description ILIKE :kw)"
            )
            params["kw"] = f"%{keyword}%"
        if language:
            conditions.append("language = :lang")
            params["lang"] = language

        where = " AND ".join(conditions)
        query = text(f"""
            SELECT id::text, title, title_ar, title_en, description,
                   size, field, file_format,
                   language, creation_date, views_count
            FROM resources_corpus
            WHERE {where}
            ORDER BY creation_date DESC
            LIMIT :lim
        """)
        rows = (await db.execute(query, params)).mappings().all()
        return [
            {
                "id": r["id"], "type": "corpus",
                "title": r["title_en"] or r["title_ar"] or r["title"],
                "description": (r["description"] or "")[:300],
                "size": r["size"], "field": r["field"],
                "format": r["file_format"],
                "language": r["language"],
                "created_at": str(r["creation_date"]) if r["creation_date"] else None,
                "views": r["views_count"],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Events search
    # ------------------------------------------------------------------

    async def search_events(
        self,
        db: AsyncSession,
        keyword: Optional[str] = None,
        event_type: Optional[str] = None,
        upcoming_only: bool = False,
        limit: int = 10,
    ) -> List[Dict]:
        conditions = ["approval_status = 'approved'"]
        params: Dict = {"lim": limit}

        if keyword:
            conditions.append(
                "(title ILIKE :kw OR title_ar ILIKE :kw OR title_en ILIKE :kw "
                "OR description ILIKE :kw OR domains ILIKE :kw)"
            )
            params["kw"] = f"%{keyword}%"
        if event_type:
            conditions.append("event_type = :etype")
            params["etype"] = event_type
        if upcoming_only:
            conditions.append("start_date >= CURRENT_DATE")

        where = " AND ".join(conditions)
        query = text(f"""
            SELECT id::text, title, title_ar, title_en,
                   description, event_type, domains, location,
                   start_date, end_date, submission_deadline,
                   website, contact_email, created_at
            FROM events_event
            WHERE {where}
            ORDER BY start_date DESC
            LIMIT :lim
        """)
        rows = (await db.execute(query, params)).mappings().all()
        return [
            {
                "id": r["id"], "type": "event",
                "title": r["title_en"] or r["title_ar"] or r["title"],
                "description": (r["description"] or "")[:300],
                "event_type": r["event_type"],
                "domains": r["domains"],
                "location": r["location"],
                "start_date": str(r["start_date"]) if r["start_date"] else None,
                "end_date": str(r["end_date"]) if r["end_date"] else None,
                "submission_deadline": str(r["submission_deadline"]) if r["submission_deadline"] else None,
                "website": r["website"],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Institutions
    # ------------------------------------------------------------------

    async def search_institutions(
        self,
        db: AsyncSession,
        keyword: Optional[str] = None,
        institution_type: Optional[str] = None,
        country_code: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        conditions: List[str] = []
        params: Dict = {"lim": limit}

        if keyword:
            conditions.append(
                "(i.name ILIKE :kw OR i.name_ar ILIKE :kw OR i.name_en ILIKE :kw "
                "OR i.description ILIKE :kw OR i.city ILIKE :kw)"
            )
            params["kw"] = f"%{keyword}%"
        if institution_type:
            conditions.append("i.type = :itype")
            params["itype"] = institution_type
        if country_code:
            conditions.append("c.code = :cc")
            params["cc"] = country_code

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        query = text(f"""
            SELECT i.id::text, i.name, i.name_ar, i.name_en,
                   i.type, i.city, i.city_ar, i.city_en,
                   i.website, i.description,
                   c.name_en AS country_name, c.code AS country_code
            FROM institutions_institution i
            LEFT JOIN institutions_country c ON i.country_id = c.id
            {where}
            ORDER BY i.name
            LIMIT :lim
        """)
        rows = (await db.execute(query, params)).mappings().all()
        return [
            {
                "id": r["id"], "type": "institution",
                "name": r["name_en"] or r["name_ar"] or r["name"],
                "institution_type": r["type"],
                "city": r["city_en"] or r["city_ar"] or r["city"],
                "country": r["country_name"],
                "country_code": r["country_code"],
                "website": r["website"],
                "description": (r["description"] or "")[:300],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    async def search_projects(
        self,
        db: AsyncSession,
        keyword: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        conditions = ["approval_status = 'approved'"]
        params: Dict = {"lim": limit}

        if keyword:
            conditions.append(
                "(title ILIKE :kw OR title_ar ILIKE :kw OR title_en ILIKE :kw "
                "OR description ILIKE :kw)"
            )
            params["kw"] = f"%{keyword}%"
        if status:
            conditions.append("status = :st")
            params["st"] = status

        where = " AND ".join(conditions)
        query = text(f"""
            SELECT p.id::text, p.title, p.title_ar, p.title_en,
                   p.description, p.status, p.date_start, p.date_end,
                   p.created_at,
                   i.name AS institution_name
            FROM projects_project p
            LEFT JOIN institutions_institution i ON p.institution_id = i.id
            WHERE {where}
            ORDER BY p.date_start DESC NULLS LAST
            LIMIT :lim
        """)
        rows = (await db.execute(query, params)).mappings().all()
        return [
            {
                "id": r["id"], "type": "project",
                "title": r["title_en"] or r["title_ar"] or r["title"],
                "description": (r["description"] or "")[:300],
                "status": r["status"],
                "institution": r["institution_name"],
                "date_start": str(r["date_start"]) if r["date_start"] else None,
                "date_end": str(r["date_end"]) if r["date_end"] else None,
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Author / user lookup
    # ------------------------------------------------------------------

    async def search_authors(
        self,
        db: AsyncSession,
        keyword: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        conditions = ["u.is_active = true", "u.status = 'active'"]
        params: Dict = {"lim": limit}

        if keyword:
            conditions.append(
                "(u.full_name ILIKE :kw OR u.full_name_ar ILIKE :kw "
                "OR u.full_name_en ILIKE :kw OR u.email ILIKE :kw)"
            )
            params["kw"] = f"%{keyword}%"

        where = " AND ".join(conditions)
        query = text(f"""
            SELECT u.id::text, u.full_name, u.full_name_ar, u.full_name_en,
                   u.email, u.bio,
                   i.name AS institution_name
            FROM accounts_customuser u
            LEFT JOIN institutions_institution i ON u.institution_id = i.id
            WHERE {where}
            ORDER BY u.full_name
            LIMIT :lim
        """)
        rows = (await db.execute(query, params)).mappings().all()
        return [
            {
                "id": r["id"], "type": "author",
                "name": r["full_name_en"] or r["full_name_ar"] or r["full_name"] or "",
                "email": r["email"],
                "bio": (r["bio"] or "")[:200],
                "institution": r["institution_name"],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Article-specific queries (timestamps, DOI, journal)
    # ------------------------------------------------------------------

    async def get_article_details(
        self, db: AsyncSession, keyword: str, limit: int = 5,
    ) -> List[Dict]:
        """Look up articles by title keyword with publication metadata."""
        query = text("""
            SELECT d.id::text, d.title, d.title_ar, d.title_en,
                   d.creation_date, d.document_type,
                   a.publication_date, a.journal, a.doi
            FROM resources_document d
            LEFT JOIN resources_article a ON a.document_id = d.id
            WHERE d.approval_status = 'approved'
              AND d.document_type = 'article'
              AND (d.title ILIKE :kw OR d.title_ar ILIKE :kw
                   OR d.title_en ILIKE :kw)
            ORDER BY a.publication_date DESC NULLS LAST
            LIMIT :lim
        """)
        rows = (await db.execute(query, {"kw": f"%{keyword}%", "lim": limit})).mappings().all()
        return [
            {
                "id": r["id"], "type": "article",
                "title": r["title_en"] or r["title_ar"] or r["title"],
                "created_at": str(r["creation_date"]) if r["creation_date"] else None,
                "publication_date": str(r["publication_date"]) if r["publication_date"] else None,
                "journal": r["journal"],
                "doi": r["doi"],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Platform statistics (for general navigation)
    # ------------------------------------------------------------------

    async def get_platform_stats(self, db: AsyncSession) -> Dict:
        """Return platform-wide statistics."""
        query = text("""
            SELECT
                (SELECT COUNT(*) FROM resources_course WHERE approval_status='approved') AS courses,
                (SELECT COUNT(*) FROM resources_document WHERE approval_status='approved') AS documents,
                (SELECT COUNT(*) FROM resources_nlptool WHERE approval_status='approved') AS tools,
                (SELECT COUNT(*) FROM resources_corpus WHERE approval_status='approved') AS corpora,
                (SELECT COUNT(*) FROM events_event WHERE approval_status='approved') AS events,
                (SELECT COUNT(*) FROM projects_project WHERE approval_status='approved') AS projects,
                (SELECT COUNT(*) FROM institutions_institution) AS institutions,
                (SELECT COUNT(*) FROM accounts_customuser WHERE is_active=true) AS users
        """)
        row = (await db.execute(query)).mappings().first()
        if not row:
            return {}
        return {
            "courses": row["courses"],
            "documents": row["documents"],
            "tools": row["tools"],
            "corpora": row["corpora"],
            "events": row["events"],
            "projects": row["projects"],
            "institutions": row["institutions"],
            "users": row["users"],
        }

    # ------------------------------------------------------------------
    # Navigation assistance
    # ------------------------------------------------------------------

    async def get_navigation_help(self, query_text: str) -> Dict:
        """Return navigation hints based on what the user is looking for."""
        q = query_text.lower()
        nav: Dict = {"suggestions": []}

        mapping = {
            "course": {"section": "Resources > Courses", "url": "/resources/courses/"},
            "article": {"section": "Resources > Articles", "url": "/resources/articles/"},
            "thesis": {"section": "Resources > Theses", "url": "/resources/theses/"},
            "memoir": {"section": "Resources > Memoirs", "url": "/resources/memoirs/"},
            "tool": {"section": "Resources > NLP Tools", "url": "/resources/tools/"},
            "corpus": {"section": "Resources > Corpora", "url": "/resources/corpora/"},
            "corpora": {"section": "Resources > Corpora", "url": "/resources/corpora/"},
            "event": {"section": "Events", "url": "/events/"},
            "conference": {"section": "Events", "url": "/events/"},
            "workshop": {"section": "Events", "url": "/events/"},
            "institution": {"section": "Institutions", "url": "/institutions/"},
            "university": {"section": "Institutions", "url": "/institutions/"},
            "project": {"section": "Projects", "url": "/projects/"},
            "forum": {"section": "Forum", "url": "/forum/"},
            "post": {"section": "QA / Posts", "url": "/QA/"},
            "question": {"section": "QA / Posts", "url": "/QA/"},
        }

        for keyword, info in mapping.items():
            if keyword in q:
                nav["suggestions"].append(info)

        # Deduplicate by url
        seen = set()
        unique = []
        for s in nav["suggestions"]:
            if s["url"] not in seen:
                seen.add(s["url"])
                unique.append(s)
        nav["suggestions"] = unique

        return nav

    # ------------------------------------------------------------------
    # Unified search (combine all sources)
    # ------------------------------------------------------------------

    async def search_by_type(
        self,
        db: AsyncSession,
        keyword: str,
        resource_type: Optional[str] = None,
        language: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        """Dispatch search to the right handler based on resource_type.

        Keeps routing logic inside the service (not the controller).
        """
        if resource_type in ("event",):
            return await self.search_events(db, keyword=keyword, limit=limit)
        if resource_type in ("institution", "university"):
            return await self.search_institutions(db, keyword=keyword, limit=limit)
        if resource_type in ("project",):
            return await self.search_projects(db, keyword=keyword, limit=limit)
        if resource_type in ("author", "researcher"):
            return await self.search_authors(db, keyword=keyword, limit=limit)
        return await self.search_resources(
            db, keyword=keyword, resource_type=resource_type,
            language=language, limit=limit,
        )

    async def unified_search(
        self,
        db: AsyncSession,
        keyword: str,
        limit: int = 10,
    ) -> List[Dict]:
        """Search across all Django platform tables."""
        results: List[Dict] = []

        resources = await self.search_resources(db, keyword=keyword, limit=5)
        results.extend(resources)

        events = await self.search_events(db, keyword=keyword, limit=3)
        results.extend(events)

        institutions = await self.search_institutions(db, keyword=keyword, limit=3)
        results.extend(institutions)

        projects = await self.search_projects(db, keyword=keyword, limit=3)
        results.extend(projects)

        return results[:limit]


# Singleton
_platform_query_service: Optional[PlatformQueryService] = None


def get_platform_query_service() -> PlatformQueryService:
    global _platform_query_service
    if _platform_query_service is None:
        _platform_query_service = PlatformQueryService()
    return _platform_query_service
