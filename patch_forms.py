"""Patch CustomUserChangeForm to remove avatar field."""

path = '/app/accounts/forms.py'
with open(path, 'r') as f:
    content = f.read()

changes = 0

# 1. Remove avatar field declaration
avatar_decl = """    avatar = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        label=_("Profile Picture"),
        help_text=_("Recommended size: 200x200 pixels. Max file size: 2MB")
    )

    class Meta:"""

if avatar_decl in content:
    content = content.replace(avatar_decl, "    class Meta:")
    changes += 1
    print("1. Removed avatar field declaration")
else:
    print("1. Avatar field declaration already removed")

# 2. Remove 'avatar' from Meta.fields
old_fields = "'email', 'institution', 'bio', 'bio_ar', 'bio_en', 'avatar',"
new_fields = "'email', 'institution', 'bio', 'bio_ar', 'bio_en',"
if old_fields in content:
    content = content.replace(old_fields, new_fields)
    changes += 1
    print("2. Removed avatar from Meta.fields")
else:
    print("2. Avatar already removed from Meta.fields")

# 3. Remove clean_avatar method
clean_avatar = '''    def clean_avatar(self):
        """Validate avatar image."""
        avatar = self.cleaned_data.get('avatar')
        if avatar:
            # Check file size (2MB limit)
            if avatar.size > 2 * 1024 * 1024:
                raise forms.ValidationError(_("Image file size must be less than 2MB."))
            
            # Check file extension
            allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp']
            file_ext = avatar.name.split('.')[-1].lower()
            if file_ext not in allowed_extensions:
                raise forms.ValidationError(
                    _("Allowed image formats: %(formats)s") % {'formats': ', '.join(allowed_extensions)}
                )
        return avatar

    def save'''

clean_avatar_replacement = "    def save"

if clean_avatar in content:
    content = content.replace(clean_avatar, clean_avatar_replacement)
    changes += 1
    print("3. Removed clean_avatar method")
else:
    print("3. clean_avatar already removed")

if changes > 0:
    with open(path, 'w') as f:
        f.write(content)
    print(f"\nDONE - {changes} changes applied")
else:
    print("\nNO CHANGES NEEDED - forms.py already patched")

# Verify
with open(path, 'r') as f:
    final = f.read()
print(f"avatar count in file: {final.count('avatar')}")
