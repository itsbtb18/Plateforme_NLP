"""Patch ProfileEditView to add form_valid with avatar handling."""
import re

path = '/app/accounts/views.py'
with open(path, 'r') as f:
    content = f.read()

if 'avatar' in content and 'form_valid' in content.split('ProfileEditView')[1] if 'ProfileEditView' in content else False:
    print('ALREADY PATCHED')
    exit(0)

# Find the ProfileEditView class and its form_invalid method
# Insert form_valid BEFORE form_invalid
old_block = """    def get_success_url(self) -> str:
        messages.success(self.request, _("Your profile has been updated successfully."))
        return reverse('accounts:profile', kwargs={'pk': self.get_object().pk})

    def form_invalid(self, form: Any) -> Any:
        messages.error(self.request, _("Please correct the errors in the form."))
        return super().form_invalid(form)"""

new_block = """    def get_success_url(self) -> str:
        messages.success(self.request, _("Your profile has been updated successfully."))
        return reverse('accounts:profile', kwargs={'pk': self.get_object().pk})

    def form_valid(self, form):
        import os as _os
        user = form.save(commit=False)
        # Avatar removal
        if self.request.POST.get('avatar-clear') == 'on':
            if user.avatar:
                if user.avatar.storage.exists(user.avatar.name):
                    user.avatar.storage.delete(user.avatar.name)
                user.avatar = None
        # Avatar upload
        avatar_file = self.request.FILES.get('avatar')
        if avatar_file:
            if avatar_file.size > 2 * 1024 * 1024:
                form.add_error(None, _("Image file size must be less than 2MB."))
                return self.form_invalid(form)
            allowed = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
            ext = _os.path.splitext(avatar_file.name)[1].lstrip('.').lower()
            if ext not in allowed:
                form.add_error(None, _("Allowed image formats: %(formats)s") % {'formats': ', '.join(sorted(allowed))})
                return self.form_invalid(form)
            if user.avatar:
                if user.avatar.storage.exists(user.avatar.name):
                    user.avatar.storage.delete(user.avatar.name)
            user.avatar = avatar_file
        user.save()
        return redirect(self.get_success_url())

    def form_invalid(self, form: Any) -> Any:
        messages.error(self.request, _("Please correct the errors in the form."))
        return super().form_invalid(form)"""

# Only replace the LAST occurrence (in ProfileEditView, not in other views)
# Find the position of ProfileEditView
pev_pos = content.find('class ProfileEditView')
if pev_pos == -1:
    print('ERROR: ProfileEditView not found')
    exit(1)

# Search for old_block only after ProfileEditView
after_pev = content[pev_pos:]
if old_block in after_pev:
    patched_after = after_pev.replace(old_block, new_block, 1)
    content = content[:pev_pos] + patched_after
    with open(path, 'w') as f:
        f.write(content)
    print('PATCHED OK - form_valid added to ProfileEditView')
else:
    print('OLD BLOCK NOT FOUND - showing ProfileEditView section:')
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'ProfileEditView' in line:
            for j in range(i, min(len(lines), i+30)):
                print(f'{j+1}: {lines[j]}')
            break
