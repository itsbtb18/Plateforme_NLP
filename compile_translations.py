#!/usr/bin/env python
import polib
import os

# Path to the Arabic .po file
po_file = r"d:\Plateforme_NLP\Plateforme\locale\ar\LC_MESSAGES\django.po"
mo_file = r"d:\Plateforme_NLP\Plateforme\locale\ar\LC_MESSAGES\django.mo"

# Load the .po file
po = polib.pofile(po_file)

# Save as .mo file
po.save_as_mofile(mo_file)

print(f"✓ Successfully compiled {po_file} to {mo_file}")
print(f"✓ Total entries: {len(po.translated_entries())}")
