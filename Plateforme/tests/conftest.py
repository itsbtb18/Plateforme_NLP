import socket
from datetime import date

import factory
import pytest
import responses
from django.contrib.auth import get_user_model
from django.utils import timezone

from QA.models import Post
from events.models import Event
from institutions.models import Country, Institution
from resources.models import Course, NLPTool
from scraping.models import ScrapingRun


pytestmark = [pytest.mark.django_db]


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: marks integration tests that may be slow",
    )


@pytest.fixture
def mocked_http():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        yield rsps


@pytest.fixture
def allow_external_dns(monkeypatch):
    def _fake_getaddrinfo(hostname, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(socket, "getaddrinfo", _fake_getaddrinfo)


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    full_name_en = factory.Faker("name")
    full_name_ar = "مستخدم تجريبي"
    is_active = True

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        value = extracted or "testpass123"
        obj.set_password(value)
        if create:
            obj.save(update_fields=["password"])


class CountryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Country

    name_en = "Algeria"
    name_ar = "الجزائر"
    code = factory.Sequence(lambda n: f"{chr(65 + (n % 26))}{chr(65 + ((n + 1) % 26))}")


class InstitutionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Institution

    name = factory.Sequence(lambda n: f"Institution {n}")
    name_en = factory.SelfAttribute("name")
    name_ar = "مؤسسة"
    acronym = factory.Sequence(lambda n: f"I{n}")
    type = "University"
    country = factory.SubFactory(CountryFactory)
    city = "Algiers"
    city_en = "Algiers"
    city_ar = "الجزائر"
    website = factory.Sequence(lambda n: f"https://inst{n}.example.org")
    email = factory.Sequence(lambda n: f"contact{n}@inst.example.org")
    address = "Address"
    address_en = "Address"
    address_ar = "عنوان"
    description = "Institution description"
    description_en = "Institution description"
    description_ar = "وصف المؤسسة"
    created_by = factory.SubFactory(UserFactory)
    approval_status = "approved"
    ror_id = factory.Sequence(lambda n: f"0{n:05d}x{n % 10}")


class EventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Event

    title = factory.Sequence(lambda n: f"Event {n}")
    title_en = factory.SelfAttribute("title")
    title_ar = "حدث"
    description = "Event description"
    description_en = "Event description"
    description_ar = "وصف الحدث"
    event_type = "conference"
    domains = "nlp"
    location = "Algiers"
    start_date = factory.LazyFunction(lambda: date(2026, 10, 10))
    end_date = factory.LazyFunction(lambda: date(2026, 10, 12))
    website = factory.Sequence(lambda n: f"https://event{n}.example.org")
    organizer = factory.SubFactory(InstitutionFactory)
    contact_email = factory.Sequence(lambda n: f"events{n}@example.org")
    created_by = factory.SelfAttribute("organizer.created_by")
    approval_status = "approved"


class NLPToolFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NLPTool

    title = factory.Sequence(lambda n: f"Tool {n}")
    title_en = factory.SelfAttribute("title")
    title_ar = "أداة"
    description = "Tool description"
    description_en = "Tool description"
    description_ar = "وصف الأداة"
    tool_type = "tokenization"
    version = "1.0"
    access_link = factory.Sequence(lambda n: f"https://tool{n}.example.org")
    github_url = factory.Sequence(lambda n: f"https://github.com/example/tool{n}")
    supported_languages = "ar"
    language = "en"
    author = factory.SubFactory(UserFactory)
    approval_status = "approved"


class CourseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Course

    title = factory.Sequence(lambda n: f"Course {n}")
    title_en = factory.SelfAttribute("title")
    title_ar = "دورة"
    description = "Course description\nInstructor: Alice Smith"
    description_en = "Course description\nInstructor: Alice Smith"
    description_ar = "وصف الدورة"
    field = "nlp"
    academic_level = "master"
    teacher = factory.SubFactory(UserFactory)
    institution = factory.SubFactory(InstitutionFactory)
    academic_year = "2025-2026"
    access_link = factory.Sequence(lambda n: f"https://course{n}.example.org")
    author = factory.SubFactory(UserFactory)
    language = "en"
    approval_status = "approved"


class PostFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Post

    author = factory.SubFactory(UserFactory)
    title = factory.Sequence(lambda n: f"Post {n}")
    title_en = factory.SelfAttribute("title")
    content = "Post content"
    content_en = "Post content"
    slug = factory.Sequence(lambda n: f"post-{n}")
    approval_status = "approved"


@pytest.fixture(name="UserFactory")
def fixture_user_factory():
    return UserFactory


@pytest.fixture(name="CountryFactory")
def fixture_country_factory():
    return CountryFactory


@pytest.fixture(name="InstitutionFactory")
def fixture_institution_factory():
    return InstitutionFactory


@pytest.fixture(name="EventFactory")
def fixture_event_factory():
    return EventFactory


@pytest.fixture(name="NLPToolFactory")
def fixture_nlp_tool_factory():
    return NLPToolFactory


@pytest.fixture(name="CourseFactory")
def fixture_course_factory():
    return CourseFactory


@pytest.fixture(name="PostFactory")
def fixture_post_factory():
    return PostFactory


@pytest.fixture
def scraping_run():
    return ScrapingRun.objects.create(
        category="events",
        status="running",
        started_at=timezone.now(),
    )
