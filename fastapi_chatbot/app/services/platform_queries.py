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
        if not resource_type or resource_type in (
            "document",
            "documents",
            "article",
            "thesis",
            "memoir",
        ):
            results.extend(
                await self._search_documents(
                    db, keyword, resource_type, language, limit
                )
            )
        if not resource_type or resource_type in ("tool", "tools", "nlptool"):
            results.extend(await self._search_tools(db, keyword, language, limit))
        if not resource_type or resource_type in ("corpus", "corpora"):
            results.extend(await self._search_corpora(db, keyword, language, limit))

        results.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return results[:limit]

    async def _search_courses(
        self,
        db: AsyncSession,
        keyword: Optional[str],
        language: Optional[str],
        limit: int,
    ) -> List[Dict]:
        conditions = ["approval_status = 'approved'"]
        params: Dict = {"lim": limit}

        if keyword:
<<<<<<< HEAD
            words = keyword.split()
            for i, word in enumerate(words):
                conditions.append(
                    f"(title ILIKE :kw_course{i} OR title_ar ILIKE :kw_course{i} OR title_en ILIKE :kw_course{i} "
                    f"OR description ILIKE :kw_course{i})"
                )
                params[f"kw_course{i}"] = f"%{word}%"
=======
            conditions.append(
                "(title ILIKE :kw OR title_ar ILIKE :kw OR title_en ILIKE :kw "
                "OR description ILIKE :kw)"
            )
            params["kw"] = f"%{keyword}%"
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
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
                "id": r["id"],
                "type": "course",
                "title": r["title_en"] or r["title_ar"] or r["title"],
                "description": (r["description"] or "")[:300],
                "url": f"/resources/course/{r['id']}/",
                "field": r["field"],
                "level": r["academic_level"],
                "academic_year": r["academic_year"],
                "language": r["language"],
                "created_at": str(r["creation_date"]) if r["creation_date"] else None,
                "views": r["views_count"],
            }
            for r in rows
        ]

    async def _search_documents(
        self,
        db: AsyncSession,
        keyword: Optional[str],
        doc_type: Optional[str],
        language: Optional[str],
        limit: int,
    ) -> List[Dict]:
        conditions = ["approval_status = 'approved'"]
        params: Dict = {"lim": limit}

        if keyword:
<<<<<<< HEAD
            words = keyword.split()
            for i, word in enumerate(words):
                conditions.append(
                    f"(title ILIKE :kw{i} OR title_ar ILIKE :kw{i} OR title_en ILIKE :kw{i} "
                    f"OR description ILIKE :kw{i})"
                )
                params[f"kw{i}"] = f"%{word}%"
=======
            conditions.append(
                "(title ILIKE :kw OR title_ar ILIKE :kw OR title_en ILIKE :kw "
                "OR description ILIKE :kw)"
            )
            params["kw"] = f"%{keyword}%"
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        if doc_type in ("article", "thesis", "memoir"):
            conditions.append("document_type = :dtype")
            params["dtype"] = doc_type
        if language:
            conditions.append("language = :lang")
            params["lang"] = language

        where = " AND ".join(conditions)
        query = text(f"""
            SELECT id::text, title, title_ar, title_en, description,
<<<<<<< HEAD
                   document_type, uploaded_file, language,
=======
                   document_type, file_format, language,
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
                   creation_date, views_count
            FROM resources_document
            WHERE {where}
            ORDER BY creation_date DESC
            LIMIT :lim
        """)
        rows = (await db.execute(query, params)).mappings().all()
        return [
            {
                "id": r["id"],
                "type": "document",
                "title": r["title_en"] or r["title_ar"] or r["title"],
                "description": (r["description"] or "")[:300],
                "url": f"/resources/article/{r['id']}/",
                "document_type": r["document_type"],
<<<<<<< HEAD
                "format": r["uploaded_file"].split(".")[-1] if r["uploaded_file"] else None,
=======
                "format": r["file_format"],
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
                "language": r["language"],
                "created_at": str(r["creation_date"]) if r["creation_date"] else None,
                "views": r["views_count"],
            }
            for r in rows
        ]

    async def _search_tools(
        self,
        db: AsyncSession,
        keyword: Optional[str],
        language: Optional[str],
        limit: int,
    ) -> List[Dict]:
        conditions = ["approval_status = 'approved'"]
        params: Dict = {"lim": limit}

        if keyword:
<<<<<<< HEAD
            words = keyword.split()
            for i, word in enumerate(words):
                conditions.append(
                    f"(title ILIKE :kw_tool{i} OR title_ar ILIKE :kw_tool{i} OR title_en ILIKE :kw_tool{i} "
                    f"OR description ILIKE :kw_tool{i})"
                )
                params[f"kw_tool{i}"] = f"%{word}%"
=======
            conditions.append(
                "(title ILIKE :kw OR title_ar ILIKE :kw OR title_en ILIKE :kw "
                "OR description ILIKE :kw)"
            )
            params["kw"] = f"%{keyword}%"
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
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
                "id": r["id"],
                "type": "tool",
                "title": r["title_en"] or r["title_ar"] or r["title"],
                "description": (r["description"] or "")[:300],
                "url": f"/resources/tool/{r['id']}/",
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
        self,
        db: AsyncSession,
        keyword: Optional[str],
        language: Optional[str],
        limit: int,
    ) -> List[Dict]:
        conditions = ["approval_status = 'approved'"]
        params: Dict = {"lim": limit}

        if keyword:
<<<<<<< HEAD
            words = keyword.split()
            for i, word in enumerate(words):
                conditions.append(
                    f"(title ILIKE :kw_corp{i} OR title_ar ILIKE :kw_corp{i} OR title_en ILIKE :kw_corp{i} "
                    f"OR description ILIKE :kw_corp{i})"
                )
                params[f"kw_corp{i}"] = f"%{word}%"
=======
            conditions.append(
                "(title ILIKE :kw OR title_ar ILIKE :kw OR title_en ILIKE :kw "
                "OR description ILIKE :kw)"
            )
            params["kw"] = f"%{keyword}%"
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
        if language:
            conditions.append("language = :lang")
            params["lang"] = language

        where = " AND ".join(conditions)
        query = text(f"""
            SELECT id::text, title, title_ar, title_en, description,
                                     field,
                   language, creation_date, views_count
            FROM resources_corpus
            WHERE {where}
            ORDER BY creation_date DESC
            LIMIT :lim
        """)
        rows = (await db.execute(query, params)).mappings().all()
        return [
            {
                "id": r["id"],
                "type": "corpus",
                "title": r["title_en"] or r["title_ar"] or r["title"],
                "description": (r["description"] or "")[:300],
                "url": f"/resources/corpus/{r['id']}/",
                "field": r["field"],
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
<<<<<<< HEAD
            words = keyword.split()
            for i, word in enumerate(words):
                conditions.append(
                    f"(title ILIKE :kw_event{i} OR title_ar ILIKE :kw_event{i} OR title_en ILIKE :kw_event{i} "
                    f"OR description ILIKE :kw_event{i} OR domains ILIKE :kw_event{i})"
                )
                params[f"kw_event{i}"] = f"%{word}%"
=======
            conditions.append(
                "(title ILIKE :kw OR title_ar ILIKE :kw OR title_en ILIKE :kw "
                "OR description ILIKE :kw OR domains ILIKE :kw)"
            )
            params["kw"] = f"%{keyword}%"
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
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
                "id": r["id"],
                "type": "event",
                "title": r["title_en"] or r["title_ar"] or r["title"],
                "description": (r["description"] or "")[:300],
                "url": f"/events/{r['id']}/",
                "event_type": r["event_type"],
                "domains": r["domains"],
                "location": r["location"],
                "start_date": str(r["start_date"]) if r["start_date"] else None,
                "end_date": str(r["end_date"]) if r["end_date"] else None,
                "submission_deadline": str(r["submission_deadline"])
                if r["submission_deadline"]
                else None,
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
<<<<<<< HEAD
            words = keyword.split()
            for i, word in enumerate(words):
                conditions.append(
                    f"(i.name ILIKE :kw{i} OR i.name_ar ILIKE :kw{i} OR i.name_en ILIKE :kw{i} "
                    f"OR i.description ILIKE :kw{i} OR i.city ILIKE :kw{i})"
                )
                params[f"kw{i}"] = f"%{word}%"
=======
            conditions.append(
                "(i.name ILIKE :kw OR i.name_ar ILIKE :kw OR i.name_en ILIKE :kw "
                "OR i.description ILIKE :kw OR i.city ILIKE :kw)"
            )
            params["kw"] = f"%{keyword}%"
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
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
                "id": r["id"],
                "type": "institution",
                "name": r["name_en"] or r["name_ar"] or r["name"],
                "url": f"/institutions/{r['id']}/",
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
<<<<<<< HEAD
        conditions = ["p.approval_status = 'approved'"]
        params: Dict = {"lim": limit}

        if keyword:
            words = keyword.split()
            for i, word in enumerate(words):
                conditions.append(
                    f"(p.title ILIKE :kw_proj{i} OR p.title_ar ILIKE :kw_proj{i} OR p.title_en ILIKE :kw_proj{i} "
                    f"OR p.description ILIKE :kw_proj{i})"
                )
                params[f"kw_proj{i}"] = f"%{word}%"
        if status:
            conditions.append("p.status = :st")
=======
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
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
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
                "id": r["id"],
                "type": "project",
                "title": r["title_en"] or r["title_ar"] or r["title"],
                "description": (r["description"] or "")[:300],
                "url": f"/projects/{r['id']}/",
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
<<<<<<< HEAD
            words = keyword.split()
            for i, word in enumerate(words):
                conditions.append(
                    f"(u.full_name ILIKE :kw_auth{i} OR u.full_name_ar ILIKE :kw_auth{i} "
                    f"OR u.full_name_en ILIKE :kw_auth{i} OR u.email ILIKE :kw_auth{i} "
                    f"OR SPLIT_PART(u.email, '@', 1) ILIKE :kw_auth{i})"
                )
                params[f"kw_auth{i}"] = f"%{word}%"
=======
            conditions.append(
                "(u.full_name ILIKE :kw OR u.full_name_ar ILIKE :kw "
                "OR u.full_name_en ILIKE :kw OR u.email ILIKE :kw "
                "OR SPLIT_PART(u.email, '@', 1) ILIKE :kw)"
            )
            params["kw"] = f"%{keyword}%"
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e

        where = " AND ".join(conditions)
        query = text(f"""
            SELECT u.id::text, u.full_name, u.full_name_ar, u.full_name_en,
                   u.email, u.bio, u.bio_en, u.bio_ar, u.speciality,
                   i.name AS institution_name, i.name_en AS institution_name_en
            FROM accounts_customuser u
            LEFT JOIN institutions_institution i ON u.institution_id = i.id
            WHERE {where}
            ORDER BY u.full_name
            LIMIT :lim
        """)
        rows = (await db.execute(query, params)).mappings().all()
        return [
            {
                "id": r["id"],
                "type": "author",
                "name": r["full_name_en"] or r["full_name_ar"] or r["full_name"] or "",
                "bio": (r["bio_en"] or r["bio_ar"] or r["bio"] or "")[:300],
                "institution": r["institution_name_en"] or r["institution_name"],
                "speciality": r["speciality"],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Detailed user profile (with contributions)
    # ------------------------------------------------------------------

    async def get_user_profile_detail(
        self,
        db: AsyncSession,
        keyword: str,
    ) -> Optional[Dict]:
        """Look up a single user and return their full profile + contributions."""
        # Try exact match first (email prefix), then ILIKE
        query = text("""
            SELECT u.id::text, u.full_name, u.full_name_ar, u.full_name_en,
                   u.email, u.bio, u.bio_en, u.bio_ar, u.speciality,
                   u.date_joined,
                   i.name AS institution_name, i.name_en AS institution_name_en,
                   i.city AS institution_city, i.city_en AS institution_city_en
            FROM accounts_customuser u
            LEFT JOIN institutions_institution i ON u.institution_id = i.id
            WHERE u.is_active = true
              AND (u.full_name ILIKE :kw OR u.full_name_ar ILIKE :kw
                   OR u.full_name_en ILIKE :kw OR u.email ILIKE :kw
                   OR SPLIT_PART(u.email, '@', 1) ILIKE :kw)
            ORDER BY
                CASE WHEN SPLIT_PART(u.email, '@', 1) ILIKE :exact THEN 0
                     WHEN u.full_name_en ILIKE :exact THEN 1
                     ELSE 2 END
            LIMIT 1
        """)
        row = (
            (await db.execute(query, {"kw": f"%{keyword}%", "exact": f"%{keyword}%"}))
            .mappings()
            .first()
        )
        if not row:
            return None

        user_id = row["id"]
        profile: Dict = {
            "type": "user_profile",
            "id": user_id,
            "name": row["full_name_en"]
            or row["full_name_ar"]
            or row["full_name"]
            or "",
            "name_ar": row["full_name_ar"] or "",
            "bio": row["bio_en"] or row["bio_ar"] or row["bio"] or "",
            "speciality": row["speciality"] or "",
            "institution": row["institution_name_en"] or row["institution_name"] or "",
            "institution_city": row["institution_city_en"]
            or row["institution_city"]
            or "",
            "date_joined": str(row["date_joined"]) if row["date_joined"] else None,
        }

        # Contributions: resources authored
        contributions = await self._get_user_contributions(db, user_id)
        profile["contributions"] = contributions

        return profile

    async def _get_user_contributions(self, db: AsyncSession, user_id: str) -> Dict:
        """Fetch a user's contributions across all content types."""
        contribs: Dict = {}

        # Courses
        q = text("""
            SELECT id::text, title, title_en, title_ar, creation_date
            FROM resources_course
            WHERE author_id = :uid AND approval_status = 'approved'
            ORDER BY creation_date DESC LIMIT 10
        """)
        rows = (await db.execute(q, {"uid": user_id})).mappings().all()
        if rows:
            contribs["courses"] = [
                {
                    "title": r["title_en"] or r["title_ar"] or r["title"],
                    "date": str(r["creation_date"]) if r["creation_date"] else None,
                }
                for r in rows
            ]

        # Documents (articles, theses, memoirs)
        q = text("""
            SELECT id::text, title, title_en, title_ar, document_type, creation_date
            FROM resources_document
            WHERE author_id = :uid AND approval_status = 'approved'
            ORDER BY creation_date DESC LIMIT 10
        """)
        rows = (await db.execute(q, {"uid": user_id})).mappings().all()
        if rows:
            contribs["documents"] = [
                {
                    "title": r["title_en"] or r["title_ar"] or r["title"],
                    "type": r["document_type"],
                    "date": str(r["creation_date"]) if r["creation_date"] else None,
                }
                for r in rows
            ]

        # Tools
        q = text("""
            SELECT id::text, title, title_en, title_ar, creation_date
            FROM resources_nlptool
            WHERE author_id = :uid AND approval_status = 'approved'
            ORDER BY creation_date DESC LIMIT 10
        """)
        rows = (await db.execute(q, {"uid": user_id})).mappings().all()
        if rows:
            contribs["tools"] = [
                {
                    "title": r["title_en"] or r["title_ar"] or r["title"],
                    "date": str(r["creation_date"]) if r["creation_date"] else None,
                }
                for r in rows
            ]

        # Corpora
        q = text("""
            SELECT id::text, title, title_en, title_ar, creation_date
            FROM resources_corpus
            WHERE author_id = :uid AND approval_status = 'approved'
            ORDER BY creation_date DESC LIMIT 10
        """)
        rows = (await db.execute(q, {"uid": user_id})).mappings().all()
        if rows:
            contribs["corpora"] = [
                {
                    "title": r["title_en"] or r["title_ar"] or r["title"],
                    "date": str(r["creation_date"]) if r["creation_date"] else None,
                }
                for r in rows
            ]

        # Projects (as member or coordinator)
        q = text("""
            SELECT p.id::text, p.title, p.title_en, p.title_ar, p.status
            FROM projects_project p
            LEFT JOIN projects_projectmember pm ON pm.project_id = p.id AND pm.member_id = :uid
            WHERE (p.coordinator_id = :uid OR pm.member_id IS NOT NULL)
              AND p.approval_status = 'approved'
            ORDER BY p.date_start DESC NULLS LAST LIMIT 5
        """)
        try:
            async with db.begin_nested():
                rows = (await db.execute(q, {"uid": user_id})).mappings().all()
                if rows:
                    contribs["projects"] = [
                        {
                            "title": r["title_en"] or r["title_ar"] or r["title"],
                            "status": r["status"],
                        }
                        for r in rows
                    ]
        except Exception:
            pass  # table may not exist

        return contribs

    # ------------------------------------------------------------------
    # Current user's full contributions (by email)
    # ------------------------------------------------------------------

    async def get_current_user_contributions(
        self,
        db: AsyncSession,
        user_email: str,
        content_type: Optional[str] = None,
    ) -> Optional[Dict]:
        """Fetch the current user's contributions across ALL content types.

        Parameters
        ----------
        user_email : str
            The logged-in user's email.
        content_type : str, optional
            If given, only fetch that type (tool, course, post, project, etc.).
        """
        # Resolve user_id from email
        row = (
            (
                await db.execute(
                    text(
                        "SELECT id::text FROM accounts_customuser WHERE email = :em LIMIT 1"
                    ),
                    {"em": user_email},
                )
            )
            .mappings()
            .first()
        )
        if not row:
            return None

        uid = row["id"]
        contribs: Dict = {}
        fetch_all = content_type is None

        # --- Tools ---
        if fetch_all or content_type == "tool":
            q = text("""
                SELECT id::text, title, title_en, title_ar, creation_date
                FROM resources_nlptool
                WHERE author_id = :uid AND approval_status = 'approved'
                ORDER BY creation_date DESC LIMIT 20
            """)
            rows = (await db.execute(q, {"uid": uid})).mappings().all()
            if rows:
                contribs["tools"] = [
                    {
                        "title": r["title_en"] or r["title_ar"] or r["title"],
                        "date": str(r["creation_date"]) if r["creation_date"] else None,
                    }
                    for r in rows
                ]

        # --- Courses ---
        if fetch_all or content_type == "course":
            q = text("""
                SELECT id::text, title, title_en, title_ar, creation_date
                FROM resources_course
                WHERE author_id = :uid AND approval_status = 'approved'
                ORDER BY creation_date DESC LIMIT 20
            """)
            rows = (await db.execute(q, {"uid": uid})).mappings().all()
            if rows:
                contribs["courses"] = [
                    {
                        "title": r["title_en"] or r["title_ar"] or r["title"],
                        "date": str(r["creation_date"]) if r["creation_date"] else None,
                    }
                    for r in rows
                ]

        # --- Documents (articles, theses, memoirs) ---
        if fetch_all or content_type in ("document", "article", "thesis", "memoir"):
            q = text("""
                SELECT id::text, title, title_en, title_ar, document_type, creation_date
                FROM resources_document
                WHERE author_id = :uid AND approval_status = 'approved'
                ORDER BY creation_date DESC LIMIT 20
            """)
            rows = (await db.execute(q, {"uid": uid})).mappings().all()
            if rows:
                contribs["documents"] = [
                    {
                        "title": r["title_en"] or r["title_ar"] or r["title"],
                        "type": r["document_type"],
                        "date": str(r["creation_date"]) if r["creation_date"] else None,
                    }
                    for r in rows
                ]

        # --- Corpora ---
        if fetch_all or content_type == "corpus":
            q = text("""
                SELECT id::text, title, title_en, title_ar, creation_date
                FROM resources_corpus
                WHERE author_id = :uid AND approval_status = 'approved'
                ORDER BY creation_date DESC LIMIT 20
            """)
            rows = (await db.execute(q, {"uid": uid})).mappings().all()
            if rows:
                contribs["corpora"] = [
                    {
                        "title": r["title_en"] or r["title_ar"] or r["title"],
                        "date": str(r["creation_date"]) if r["creation_date"] else None,
                    }
                    for r in rows
                ]

        # --- Posts ---
        if fetch_all or content_type == "post":
            try:
                async with db.begin_nested():
                    q = text("""
                        SELECT id::text, title, title_en, title_ar, created_at
                        FROM "QA_post"
                        WHERE author_id = :uid AND approval_status = 'approved'
                        ORDER BY created_at DESC LIMIT 20
                    """)
                    rows = (await db.execute(q, {"uid": uid})).mappings().all()
                    if rows:
                        contribs["posts"] = [
                            {
                                "title": r["title_en"] or r["title_ar"] or r["title"],
                                "date": str(r["created_at"])
                                if r["created_at"]
                                else None,
                            }
                            for r in rows
                        ]
            except Exception:
                pass

        # --- QA Questions ---
        if fetch_all or content_type == "question":
            try:
                async with db.begin_nested():
                    q = text("""
                        SELECT id::text, title, created_at
                        FROM "QA_question"
                        WHERE author_id = :uid
                        ORDER BY created_at DESC LIMIT 20
                    """)
                    rows = (await db.execute(q, {"uid": uid})).mappings().all()
                    if rows:
                        contribs["questions"] = [
                            {
                                "title": r["title"],
                                "date": str(r["created_at"])
                                if r["created_at"]
                                else None,
                            }
                            for r in rows
                        ]
            except Exception:
                pass

        # --- QA Answers ---
        if fetch_all or content_type == "answer":
            try:
                async with db.begin_nested():
                    q = text("""
                        SELECT a.id::text, q.title AS question_title, a.created_at
                        FROM "QA_answer" a
                        JOIN "QA_question" q ON q.id = a.question_id
                        WHERE a.author_id = :uid
                        ORDER BY a.created_at DESC LIMIT 20
                    """)
                    rows = (await db.execute(q, {"uid": uid})).mappings().all()
                    if rows:
                        contribs["answers"] = [
                            {
                                "question": r["question_title"],
                                "date": str(r["created_at"])
                                if r["created_at"]
                                else None,
                            }
                            for r in rows
                        ]
            except Exception:
                pass

        # --- Projects ---
        if fetch_all or content_type == "project":
            try:
                async with db.begin_nested():
                    q = text("""
                        SELECT p.id::text, p.title, p.title_en, p.title_ar, p.status
                        FROM projects_project p
                        LEFT JOIN projects_projectmember pm ON pm.project_id = p.id AND pm.member_id = :uid
                        WHERE (p.coordinator_id = :uid OR pm.member_id IS NOT NULL)
                          AND p.approval_status = 'approved'
                        ORDER BY p.date_start DESC NULLS LAST LIMIT 10
                    """)
                    rows = (await db.execute(q, {"uid": uid})).mappings().all()
                    if rows:
                        contribs["projects"] = [
                            {
                                "title": r["title_en"] or r["title_ar"] or r["title"],
                                "status": r["status"],
                            }
                            for r in rows
                        ]
            except Exception:
                pass

        # --- Events created ---
        if fetch_all or content_type == "event":
            try:
                async with db.begin_nested():
                    q = text("""
                        SELECT id::text, title, title_en, title_ar, event_type, start_date
                        FROM events_event
                        WHERE created_by_id = :uid AND approval_status = 'approved'
                        ORDER BY start_date DESC NULLS LAST LIMIT 10
                    """)
                    rows = (await db.execute(q, {"uid": uid})).mappings().all()
                    if rows:
                        contribs["events"] = [
                            {
                                "title": r["title_en"] or r["title_ar"] or r["title"],
                                "type": r["event_type"],
                                "date": str(r["start_date"])
                                if r["start_date"]
                                else None,
                            }
                            for r in rows
                        ]
            except Exception:
                pass

        # --- Forum topics ---
        if fetch_all or content_type == "topic":
            try:
                async with db.begin_nested():
                    q = text("""
                        SELECT id::text, title, title_en, title_ar, created_at
                        FROM forum_topic
                        WHERE creator_id = :uid AND approval_status = 'approved'
                        ORDER BY created_at DESC LIMIT 10
                    """)
                    rows = (await db.execute(q, {"uid": uid})).mappings().all()
                    if rows:
                        contribs["forum_topics"] = [
                            {
                                "title": r["title_en"] or r["title_ar"] or r["title"],
                                "date": str(r["created_at"])
                                if r["created_at"]
                                else None,
                            }
                            for r in rows
                        ]
            except Exception:
                pass

        return contribs if contribs else None

    # ------------------------------------------------------------------
    # Article-specific queries (timestamps, DOI, journal)
    # ------------------------------------------------------------------

    async def get_article_details(
        self,
        db: AsyncSession,
        keyword: str,
        limit: int = 5,
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
        rows = (
            (await db.execute(query, {"kw": f"%{keyword}%", "lim": limit}))
            .mappings()
            .all()
        )
        return [
            {
                "id": r["id"],
                "type": "article",
                "title": r["title_en"] or r["title_ar"] or r["title"],
                "created_at": str(r["creation_date"]) if r["creation_date"] else None,
                "publication_date": str(r["publication_date"])
                if r["publication_date"]
                else None,
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
            "article": {
                "section": "Resources > Articles",
                "url": "/resources/articles/",
            },
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
    # Forum search
    # ------------------------------------------------------------------

    async def search_forum_topics(
        self,
        db: AsyncSession,
        keyword: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        """Search approved forum topics by keyword (title + description).

        When the keyword looks like a full sentence, extract meaningful
        words and search with OR logic so broad queries like
        "Show me forum topics about NLP" still find results.
        """
        STOP_WORDS = {
            "show",
            "me",
            "find",
            "list",
            "give",
            "get",
            "the",
            "a",
            "an",
            "is",
            "are",
            "about",
            "for",
            "in",
            "on",
            "of",
            "to",
            "and",
            "or",
            "with",
            "what",
            "which",
            "how",
            "my",
            "all",
            "any",
            "forum",
            "topic",
            "topics",
            "discussion",
            "discussions",
            "montrer",
            "trouver",
            "lister",
            "les",
            "des",
            "un",
            "une",
            "le",
            "la",
            "du",
            "de",
            "sur",
            "pour",
            "dans",
            "et",
            "ou",
            "sujet",
            "sujets",
            "منتدى",
            "موضوع",
            "مواضيع",
            "أعرض",
            "اعثر",
            "قائمة",
        }
        try:
            if keyword:
                # Extract meaningful search terms from the query
                words = [
                    w
                    for w in keyword.lower().split()
                    if w not in STOP_WORDS and len(w) > 2
                ]
                if words:
                    # Build OR conditions for each meaningful word
                    conditions = []
                    params: dict = {"lim": limit}
                    for i, w in enumerate(words[:5]):  # max 5 keywords
                        p = f"kw{i}"
                        params[p] = f"%{w}%"
                        conditions.append(
                            f"(title ILIKE :{p} OR title_en ILIKE :{p}"
                            f" OR title_ar ILIKE :{p}"
                            f" OR description ILIKE :{p} OR description_en ILIKE :{p}"
                            f" OR description_ar ILIKE :{p})"
                        )
                    where = " OR ".join(conditions)
                else:
                    # No useful words — return latest topics
                    where = None
                    params = {"lim": limit}

                if where:
                    rows = (
                        await db.execute(
                            text(f"""
                                SELECT id, title, title_en, title_ar,
                                       description, description_en, description_ar,
                                       created_at, is_closed
                                FROM forum_topic
                                WHERE approval_status = 'approved'
                                  AND ({where})
                                ORDER BY created_at DESC
                                LIMIT :lim
                            """),
                            params,
                        )
                    ).fetchall()
                else:
                    rows = (
                        await db.execute(
                            text("""
                                SELECT id, title, title_en, title_ar,
                                       description, description_en, description_ar,
                                       created_at, is_closed
                                FROM forum_topic
                                WHERE approval_status = 'approved'
                                ORDER BY created_at DESC
                                LIMIT :lim
                            """),
                            {"lim": limit},
                        )
                    ).fetchall()
            else:
                rows = (
                    await db.execute(
                        text("""
                            SELECT id, title, title_en, title_ar,
                                   description, description_en, description_ar,
                                   created_at, is_closed
                            FROM forum_topic
                            WHERE approval_status = 'approved'
                            ORDER BY created_at DESC
                            LIMIT :lim
                        """),
                        {"lim": limit},
                    )
                ).fetchall()

            return [
                {
                    "type": "forum_topic",
                    "title": r.title_en or r.title or "",
                    "description": (r.description_en or r.description or "")[:300],
                    "url": f"/forum/",
                    "status": "closed" if r.is_closed else "open",
                    "date": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows
            ]
        except Exception as e:
            logger.error("Forum search error: %s", e, exc_info=True)
            return []

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
        if resource_type in ("topic", "forum", "forum_topic"):
            return await self.search_forum_topics(db, keyword=keyword, limit=limit)
        return await self.search_resources(
            db,
            keyword=keyword,
            resource_type=resource_type,
            language=language,
            limit=limit,
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

        forum_topics = await self.search_forum_topics(db, keyword=keyword, limit=3)
        results.extend(forum_topics)

        return results[:limit]


<<<<<<< HEAD
    async def get_resource_by_id(self, db: AsyncSession, resource_id: str) -> Optional[Dict]:
        """Fetch a specific resource (article/thesis/tool/etc.) by its UUID."""
        # Try articles/documents first
        query = text("""
            SELECT id::text, title, title_ar, title_en, description,
                   document_type, uploaded_file, language,
                   creation_date, views_count
            FROM resources_document
            WHERE id = :rid
        """)
        r = (await db.execute(query, {"rid": resource_id})).mappings().first()
        if r:
            return {
                "id": r["id"],
                "type": "document",
                "title": r["title_en"] or r["title_ar"] or r["title"],
                "description": (r["description"] or "")[:300],
                "url": f"/resources/article/{r['id']}/",
                "document_type": r["document_type"],
                "format": r["uploaded_file"].split(".")[-1] if r["uploaded_file"] else None,
                "language": r["language"],
                "created_at": str(r["creation_date"]) if r["creation_date"] else None,
                "views": r["views_count"],
            }
        
        # Try tools
        query = text("""
            SELECT id::text, title, title_ar, title_en, description,
                   tool_type, version, supported_languages, language,
                   creation_date, views_count
            FROM resources_nlptool
            WHERE id = :rid
        """)
        r = (await db.execute(query, {"rid": resource_id})).mappings().first()
        if r:
            return {
                "id": r["id"],
                "type": "tool",
                "title": r["title_en"] or r["title_ar"] or r["title"],
                "description": (r["description"] or "")[:300],
                "url": f"/resources/tool/{r['id']}/",
                "tool_type": r["tool_type"],
                "version": r["version"],
                "languages": r["supported_languages"],
                "created_at": str(r["creation_date"]) if r["creation_date"] else None,
                "views": r["views_count"],
            }
        return None

    async def get_institution_by_id(self, db: AsyncSession, inst_id: str) -> Optional[Dict]:
        query = text("""
            SELECT i.id::text, i.name, i.name_ar, i.name_en,
                   i.type, i.city, i.city_ar, i.city_en,
                   i.website, i.description,
                   c.name_en AS country_name, c.code AS country_code
            FROM institutions_institution i
            LEFT JOIN institutions_country c ON i.country_id = c.id
            WHERE i.id = :iid
        """)
        r = (await db.execute(query, {"iid": inst_id})).mappings().first()
        if r:
            return {
                "id": r["id"],
                "type": "institution",
                "name": r["name_en"] or r["name_ar"] or r["name"],
                "url": f"/institutions/{r['id']}/",
                "institution_type": r["type"],
                "city": r["city_en"] or r["city_ar"] or r["city"],
                "country": r["country_name"],
                "country_code": r["country_code"],
                "website": r["website"],
                "description": (r["description"] or "")[:300],
            }
        return None

    async def get_project_by_id(self, db: AsyncSession, project_id: str) -> Optional[Dict]:
        query = text("""
            SELECT p.id::text, p.title, p.title_ar, p.title_en, p.description,
                   p.status, p.date_start, p.date_end, p.created_at,
                   i.name AS institution_name
            FROM projects_project p
            LEFT JOIN institutions_institution i ON p.institution_id = i.id
            WHERE p.id = :pid
        """)
        r = (await db.execute(query, {"pid": project_id})).mappings().first()
        if r:
            return {
                "id": r["id"],
                "type": "project",
                "title": r["title_en"] or r["title_ar"] or r["title"],
                "description": (r["description"] or "")[:300],
                "url": f"/projects/{r['id']}/",
                "status": r["status"],
                "institution": r["institution_name"],
                "start_date": str(r["date_start"]) if r["date_start"] else None,
            }
        return None

=======
>>>>>>> b0fb41f2308c0008bb552529075f0dfda842e86e
# Singleton
_platform_query_service: Optional[PlatformQueryService] = None


def get_platform_query_service() -> PlatformQueryService:
    global _platform_query_service
    if _platform_query_service is None:
        _platform_query_service = PlatformQueryService()
    return _platform_query_service
