import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'Plateforme.settings'
django.setup()
from institutions.models import Institution

# Map of English city names -> Arabic translations for Algerian cities
CITY_AR_MAP = {
    'babe zouar': 'باب الزوار',
    'bab ezzouar': 'باب الزوار',
    'babe': 'باب الزوار',
    'algiers': 'الجزائر',
    'alger': 'الجزائر',
    'oran': 'وهران',
    'constantine': 'قسنطينة',
    'annaba': 'عنابة',
    'blida': 'البليدة',
    'batna': 'باتنة',
    'setif': 'سطيف',
    'sidi bel abbes': 'سيدي بلعباس',
    'tlemcen': 'تلمسان',
    'bejaia': 'بجاية',
    'tizi ouzou': 'تيزي وزو',
    'djelfa': 'الجلفة',
    'biskra': 'بسكرة',
    'bouira': 'البويرة',
    'paris': 'باريس',
}

updated = 0
for inst in Institution.objects.all():
    city_lower = (inst.city or '').strip().lower()
    city_ar_lower = (inst.city_ar or '').strip().lower()

    # Check if city_ar is empty or non-Arabic (all ASCII)
    needs_update = False
    if not inst.city_ar or inst.city_ar.isascii():
        # Try to find Arabic translation
        lookup = city_ar_lower or city_lower
        arabic = CITY_AR_MAP.get(lookup)
        if not arabic:
            # try city field
            arabic = CITY_AR_MAP.get(city_lower)
        if arabic:
            inst.city_ar = arabic
            needs_update = True
            print(f"Updated {inst.name}: city_ar '{city_ar_lower}' -> '{arabic}'")

    # Also fix city_en if empty
    if not inst.city_en and inst.city:
        inst.city_en = inst.city
        needs_update = True

    if needs_update:
        inst.save(update_fields=['city_ar', 'city_en'])
        updated += 1

print(f"\nDone. Updated {updated} institution(s).")
