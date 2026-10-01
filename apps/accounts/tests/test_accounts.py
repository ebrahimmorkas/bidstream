import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db


def test_signup_creates_user_and_logs_in(client):
    response = client.post(
        reverse("signup"),
        {
            "email": "Ann@Example.com",
            "display_name": "annie",
            "password1": DEFAULT_PASSWORD,
            "password2": DEFAULT_PASSWORD,
        },
        follow=True,
    )

    assert response.status_code == 200
    assert response.context["user"].is_authenticated
    assert User.objects.get().email == "ann@example.com"


def test_signup_rejects_taken_display_name_case_insensitively(client):
    UserFactory(display_name="Annie")

    response = client.post(
        reverse("signup"),
        {
            "email": "new@example.com",
            "display_name": "annie",
            "password1": DEFAULT_PASSWORD,
            "password2": DEFAULT_PASSWORD,
        },
    )

    assert response.status_code == 200
    assert "display_name" in response.context["form"].errors


def test_login_with_email(client):
    user = UserFactory()

    response = client.post(reverse("login"), {"username": user.email, "password": DEFAULT_PASSWORD})

    assert response.status_code == 302


@pytest.mark.parametrize(("name", "masked"), [("johnny", "j***y"), ("ab", "a*"), ("x", "x*")])
def test_masked_name(name, masked):
    assert User(display_name=name).masked_name == masked
