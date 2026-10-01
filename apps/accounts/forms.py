from django import forms
from django.contrib.auth.forms import BaseUserCreationForm

from .models import User


class SignUpForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ["email", "display_name"]
        help_texts = {"display_name": "Shown (partially masked) next to your bids."}

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_display_name(self):
        name = self.cleaned_data["display_name"].strip()
        if User.objects.filter(display_name__iexact=name).exists():
            raise forms.ValidationError("This display name is taken.")
        return name
