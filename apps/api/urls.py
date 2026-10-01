from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from .views import AuctionViewSet

app_name = "api"

router = DefaultRouter()
router.register("auctions", AuctionViewSet, basename="auction")

urlpatterns = [
    path("auth/token/", obtain_auth_token, name="token"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="api:schema"), name="docs"),
    *router.urls,
]
