from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from pages.models import Opportunity

class HomePageTests(SimpleTestCase):
   def test_home_page_status_code(self):
      response = self.client.get('/')
      self.assertEqual(response.status_code, 200)
   def test_view_url_by_name(self):
      response = self.client.get(reverse('home'))
      self.assertEqual(response.status_code, 200)
   def test_view_uses_correct_template(self):
      response = self.client.get(reverse('home'))
      self.assertEqual(response.status_code, 200)
      self.assertTemplateUsed(response, 'home.html')

class SignupPageTests(TestCase):
   username = 'newuser'
   email = 'newuser@email.com'
   def test_signup_page_status_code(self):
      response = self.client.get('/accounts/signup/')
      self.assertEqual(response.status_code, 200)
   def test_view_url_by_name(self):
      response = self.client.get(reverse('signup'))
      self.assertEqual(response.status_code, 200)
   def test_view_uses_correct_template(self):
      response = self.client.get(reverse('signup'))
      self.assertEqual(response.status_code, 200)
      self.assertTemplateUsed(response, 'registration/signup.html')
   def test_signup_form(self):
     new_user = get_user_model().objects.create_user(
     self.username, self.email)
     self.assertEqual(get_user_model().objects.all().count(), 1)
     self.assertEqual(get_user_model().objects.all()
                      [0].username, self.username)
     self.assertEqual(get_user_model().objects.all()
                     [0].email, self.email)


class OpportunityWorkflowTests(TestCase):
   def setUp(self):
      self.user_model = get_user_model()
      self.normal_user = self.user_model.objects.create_user(
         email="member@example.com",
         password="Testpass123!",
         full_name="Member User",
      )
      self.admin_user = self.user_model.objects.create_user(
         email="admin@example.com",
         password="Testpass123!",
         full_name="Admin User",
      )
      self.admin_user.is_staff = True
      self.admin_user.is_superuser = True
      self.admin_user.save(update_fields=["is_staff", "is_superuser"])

   def _payload(self):
      return {
         "title_en": "Arabic NLP Internship",
         "title_ar": "تربص في معالجة العربية",
         "type": "internship",
         "institution_ref": "other",
         "organization_en": "Test Lab",
         "organization_ar": "مخبر تجريبي",
         "location": "Algiers",
         "mode": "hybrid",
         "level": "student",
         "deadline": "2099-12-31",
         "description": "This is a detailed opportunity description for Arabic NLP students and researchers.",
         "contact": "jobs@example.com",
         "skills_payload": '["Python","Arabic NLP"]',
      }

   def test_normal_user_submission_is_pending_and_unpublished(self):
      self.client.force_login(self.normal_user)
      response = self.client.post(reverse("pages:create_opportunity"), data=self._payload())
      self.assertEqual(response.status_code, 200)

      opportunity = Opportunity.objects.get(created_by=self.normal_user)
      self.assertEqual(opportunity.status, Opportunity.STATUS_PENDING)
      self.assertEqual(opportunity.approval_status, Opportunity.STATUS_PENDING)
      self.assertFalse(opportunity.is_published)
      self.assertEqual(opportunity.user_role, "user")

   def test_admin_submission_is_auto_approved_and_published(self):
      self.client.force_login(self.admin_user)
      response = self.client.post(reverse("pages:create_opportunity"), data=self._payload())
      self.assertEqual(response.status_code, 200)

      opportunity = Opportunity.objects.get(created_by=self.admin_user)
      self.assertEqual(opportunity.status, Opportunity.STATUS_APPROVED)
      self.assertEqual(opportunity.approval_status, Opportunity.STATUS_APPROVED)
      self.assertTrue(opportunity.is_published)
      self.assertEqual(opportunity.user_role, "admin")

   def test_only_strict_admin_can_approve_opportunity(self):
      opportunity = Opportunity.objects.create(
         title="Pending item",
         title_en="Pending item",
         title_ar="عنصر معلق",
         opportunity_type="job",
         organization_en="Org",
         organization_ar="مؤسسة",
         location="Algiers",
         mode="remote",
         level="junior",
         description="A sufficiently long description for moderation testing purposes.",
         skills=["Python"],
         contact="jobs@example.com",
         deadline="2099-12-31",
         created_by=self.normal_user,
      )

      self.client.force_login(self.normal_user)
      response = self.client.post(reverse("pages:admin_opportunity_approve", args=[opportunity.pk]))
      self.assertEqual(response.status_code, 302)
      opportunity.refresh_from_db()
      self.assertEqual(opportunity.status, Opportunity.STATUS_PENDING)

      self.client.force_login(self.admin_user)
      response = self.client.post(reverse("pages:admin_opportunity_approve", args=[opportunity.pk]))
      self.assertEqual(response.status_code, 302)
      opportunity.refresh_from_db()
      self.assertEqual(opportunity.status, Opportunity.STATUS_APPROVED)
      self.assertTrue(opportunity.is_published)
