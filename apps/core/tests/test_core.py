import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_health_check_reports_ok(client):
    response = client.get(reverse("health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": True, "cache": True}}


@pytest.mark.django_db
def test_home_page_renders(client):
    response = client.get(reverse("home"))

    assert response.status_code == 200
    assert b"BidStream" in response.content
