from django.urls import path
from . import views

urlpatterns = [
    path("list/", views.TeamListView.as_view(), name="team-list"),
    path("<int:pk>/", views.TeamDetailView.as_view(), name="team-detail"),
    path("add/", views.TeamCreateView.as_view(), name="team-create"),
    path("edit/<int:pk>/", views.TeamUpdateView.as_view(), name="team-update"),
    path("delete/<int:pk>/", views.TeamDeleteView.as_view(), name="team-delete"),
    path("teams/<int:pk>/members/", views.TeamMembersUpdateView.as_view(), name="team-members-update"),

]