#!/usr/bin/env python
"""Test script to identify form validation errors for Projects and Topics"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Plateforme'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Plateforme.settings')
django.setup()

from projects.forms import ProjectForm
from forum.forms import TopicForm
from accounts.models import CustomUser
from institutions.models import Institution
from django.utils.translation import activate

print("=" * 60)
print("FORM VALIDATION TEST - Projects and Topics")
print("=" * 60)

# Get test user
user = CustomUser.objects.first()
print(f"\n✓ Using test user: {user.email}")

# Test 1: Project Form Validation (English)
print("\n" + "=" * 60)
print("[TEST 1] Project Form - English Language")
print("=" * 60)
activate('en')

# Get first institution for testing
institution = Institution.objects.first()
if not institution:
    print("❌ ERROR: No institutions found in database!")
    print("   Please create at least one institution first.")
else:
    print(f"✓ Using institution: {institution.name_en}")
    
    project_data = {
        'title': 'Test Project English',
        'institution': institution.id,
        'description': 'Test description for project',
        'status': 'ongoing',
    }
    
    form = ProjectForm(data=project_data)
    print(f"\nForm is_valid(): {form.is_valid()}")
    
    if form.is_valid():
        print("✅ Project form validation PASSED")
        # Don't actually save, just test validation
        instance = form.save(commit=False)
        print(f"   - Title (main): {instance.title}")
        print(f"   - Title (en): {instance.title_en}")
        print(f"   - Title (ar): {instance.title_ar}")
        print(f"   - Description (main): {instance.description[:50]}...")
    else:
        print("❌ Project form validation FAILED")
        print("\nERRORS:")
        for field, errors in form.errors.items():
            print(f"   - {field}: {', '.join(errors)}")

# Test 2: Project Form Validation (Arabic)
print("\n" + "=" * 60)
print("[TEST 2] Project Form - Arabic Language")
print("=" * 60)
activate('ar')

if institution:
    project_data_ar = {
        'title': 'مشروع تجريبي',
        'institution': institution.id,
        'description': 'وصف تجريبي للمشروع',
        'status': 'ongoing',
    }
    
    form = ProjectForm(data=project_data_ar)
    print(f"\nForm is_valid(): {form.is_valid()}")
    
    if form.is_valid():
        print("✅ Project form validation PASSED (Arabic)")
        instance = form.save(commit=False)
        print(f"   - Title (main): {instance.title}")
        print(f"   - Title (ar): {instance.title_ar}")
        print(f"   - Title (en): {instance.title_en}")
    else:
        print("❌ Project form validation FAILED (Arabic)")
        print("\nERRORS:")
        for field, errors in form.errors.items():
            print(f"   - {field}: {', '.join(errors)}")

# Test 3: Topic Form Validation (English)
print("\n" + "=" * 60)
print("[TEST 3] Topic Form - English Language")
print("=" * 60)
activate('en')

topic_data = {
    'title': 'Test Topic Discussion',
    'description': 'This is a test discussion topic for the forum.',
}

form = TopicForm(data=topic_data)
print(f"\nForm is_valid(): {form.is_valid()}")

if form.is_valid():
    print("✅ Topic form validation PASSED")
    instance = form.save(commit=False)
    print(f"   - Title (main): {instance.title}")
    print(f"   - Title (en): {instance.title_en}")
    print(f"   - Title (ar): {instance.title_ar}")
    print(f"   - Description (main): {instance.description[:50]}...")
else:
    print("❌ Topic form validation FAILED")
    print("\nERRORS:")
    for field, errors in form.errors.items():
        print(f"   - {field}: {', '.join(errors)}")

# Test 4: Topic Form Validation (Arabic)
print("\n" + "=" * 60)
print("[TEST 4] Topic Form - Arabic Language")
print("=" * 60)
activate('ar')

topic_data_ar = {
    'title': 'موضوع نقاش تجريبي',
    'description': 'هذا موضوع تجريبي للمنتدى.',
}

form = TopicForm(data=topic_data_ar)
print(f"\nForm is_valid(): {form.is_valid()}")

if form.is_valid():
    print("✅ Topic form validation PASSED (Arabic)")
    instance = form.save(commit=False)
    print(f"   - Title (main): {instance.title}")
    print(f"   - Title (ar): {instance.title_ar}")
    print(f"   - Title (en): {instance.title_en}")
else:
    print("❌ Topic form validation FAILED (Arabic)")
    print("\nERRORS:")
    for field, errors in form.errors.items():
        print(f"   - {field}: {', '.join(errors)}")

# Test 5: Empty Form Submission
print("\n" + "=" * 60)
print("[TEST 5] Empty Forms - What User Might See")
print("=" * 60)

print("\n--- Empty Project Form ---")
empty_project_form = ProjectForm(data={})
if not empty_project_form.is_valid():
    print("Expected validation failure:")
    for field, errors in empty_project_form.errors.items():
        print(f"   ❌ {field}: {', '.join(errors)}")

print("\n--- Empty Topic Form ---")
empty_topic_form = TopicForm(data={})
if not empty_topic_form.is_valid():
    print("Expected validation failure:")
    for field, errors in empty_topic_form.errors.items():
        print(f"   ❌ {field}: {', '.join(errors)}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
print("\nIf all tests pass but web forms fail:")
print("1. Check browser console for JavaScript errors")
print("2. Verify form field names match exactly")
print("3. Check CSRF token is present")
print("4. Ensure form method is POST")
print("5. Look at Django runserver output for validation errors")
