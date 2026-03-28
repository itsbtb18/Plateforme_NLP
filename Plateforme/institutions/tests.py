from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Country, Institution, Specialty


class InstitutionDetailVisibilityTests(TestCase):
    def setUp(self):
        user_model = get_user_model()

        self.creator = user_model.objects.create_user(
            email="creator@example.com",
            password="test-pass-123",
            full_name_en="Creator User",
            full_name_ar="منشئ",
            is_verified=True,
        )
        self.other_user = user_model.objects.create_user(
            email="other@example.com",
            password="test-pass-123",
            full_name_en="Other User",
            full_name_ar="مستخدم",
            is_verified=True,
        )
        self.staff_user = user_model.objects.create_user(
            email="staff@example.com",
            password="test-pass-123",
            full_name_en="Staff User",
            full_name_ar="موظف",
            is_staff=True,
            is_superuser=True,
            is_verified=True,
        )

        self.country = Country.objects.create(
            name_en="Algeria",
            name_ar="الجزائر",
            code="DZ",
        )
        self.specialty = Specialty.objects.create(
            name_en="Natural Language Processing",
            name_ar="معالجة اللغة الطبيعية",
            code="NLP",
        )

        self.pending_institution = Institution.objects.create(
            name="Pending Institute",
            name_en="Pending Institute",
            name_ar="معهد قيد الانتظار",
            type="University",
            country=self.country,
            city="Algiers",
            website="https://pending.example.com",
            created_by=self.creator,
            approval_status="pending",
        )
        self.pending_institution.specialties.add(self.specialty)

        self.detail_url = reverse(
            "institutions:institution_detail",
            kwargs={"pk": self.pending_institution.pk},
        )

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url.lower())

    def test_authenticated_non_creator_gets_404_for_pending_institution(self):
        self.client.force_login(self.other_user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 404)

    def test_creator_can_view_own_pending_institution(self):
        self.client.force_login(self.creator)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)

    def test_staff_can_view_pending_institution(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
