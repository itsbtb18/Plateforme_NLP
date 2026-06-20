from django import forms
from django.utils.translation import gettext_lazy as _

from django.contrib.auth import get_user_model

from .models import Message, URL_RE, validate_chat_file

User = get_user_model()


class UserDisplayMultipleChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        full_name = (getattr(obj, "get_full_name_display", "") or "").strip()
        if full_name and full_name != obj.email:
            return full_name
        return (obj.email or "").split("@")[0]


class MessageCreateForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["content", "file_path"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "rows": 2,
                    "placeholder": _("Write a message..."),
                    "class": "dm-composer-input",
                }
            ),
            "file_path": forms.ClearableFileInput(
                attrs={
                    "class": "dm-file-input",
                    "accept": ".pdf,.jpg,.jpeg,.png,.gif,.webp,.mp4,.webm,.mov,.mp3,.wav,.ogg,.m4a,.docx,audio/*",
                }
            ),
        }

    def clean_file_path(self):
        file_obj = self.cleaned_data.get("file_path")
        if file_obj:
            validate_chat_file(file_obj)
        return file_obj

    def clean(self):
        cleaned = super().clean()
        content = (cleaned.get("content") or "").strip()
        file_obj = cleaned.get("file_path")

        if not content and not file_obj:
            raise forms.ValidationError(_("Enter a message, a link, or attach a file."))

        if file_obj:
            self.instance.message_type = Message.MessageType.FILE
        elif URL_RE.search(content):
            self.instance.message_type = Message.MessageType.LINK
        else:
            self.instance.message_type = Message.MessageType.TEXT

        return cleaned


class GroupCreateForm(forms.Form):
    group_name = forms.CharField(
        max_length=120,
        label=_("Group name"),
        widget=forms.TextInput(
            attrs={
                "class": "ig-group-input",
                "placeholder": _("Enter group name"),
            }
        ),
    )
    group_image = forms.ImageField(
        required=False,
        label=_("Group image"),
        widget=forms.FileInput(
            attrs={
                "class": "ig-group-image-picker",
                "accept": "image/*",
            }
        ),
    )
    members = UserDisplayMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        label=_("Members"),
        widget=forms.CheckboxSelectMultiple(
            attrs={
                "class": "ig-group-members-checklist",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        members_queryset = kwargs.pop("members_queryset", User.objects.none())
        super().__init__(*args, **kwargs)
        self.fields["members"].queryset = members_queryset
