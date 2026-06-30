from django.urls import path
from .views import (
    ConfirmPasswordResetView,
    MyTokenObtainPairView,
    RegisterView,
    LoginView,
    RefreshTokenView,
    RequestPasswordResetView,
    TimesheetListCreateView,
    TimesheetDetailView,
    ProjectListCreateView,
    ProjectDetailView,
    UserProjectListCreateView,
    UserProjectDetailView,
    PPTAutomationAPI,
    TimeTrackingAPI,
    TimeTrackingTemplateAPI,
    TimeTrackingEmailAPI,
    UserTimesheetListView,
    UserListAPIView,
    ValidateMultipleTimesheetView,
    PushTimesheetEmailView,
    ProjectUserRolesView,
    ProjectUsersView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh-token/", RefreshTokenView.as_view(), name="refresh-token"),
    path("token/", MyTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("users/", UserListAPIView.as_view(), name="user-list"),
    path("projects/", ProjectListCreateView.as_view(), name="project-list"),
    path("projects/<int:pk>/", ProjectDetailView.as_view(), name="project-detail"),
    path(
        "users/<int:user_id>/projects/",
        ProjectListCreateView.as_view(),
        name="user-projects",
    ),
    path(
        "user-projects/", UserProjectListCreateView.as_view(), name="user-project-list"
    ),
    path(
        "user-projects/<int:pk>/",
        UserProjectDetailView.as_view(),
        name="user-project-detail",
    ),
    path("timesheets/", TimesheetListCreateView.as_view(), name="timesheet-list"),
    path(
        "timesheets/<int:pk>/", TimesheetDetailView.as_view(), name="timesheet-detail"
    ),
    path("ppt-automation/", PPTAutomationAPI.as_view(), name="ppt-automation-api"),
    path(
        "time-tracking/validation/",
        TimeTrackingAPI.as_view(),
        name="time-tracking-validation",
    ),
    path(
        "time-tracking/templates/",
        TimeTrackingTemplateAPI.as_view(),
        name="time-tracking-templates",
    ),
    path(
        "time-tracking/templates/<str:filename>/",
        TimeTrackingTemplateAPI.as_view(),
        name="time-tracking-template-download",
    ),
    path(
        "time-tracking/send-email/",
        TimeTrackingEmailAPI.as_view(),
        name="time-tracking-email",
    ),
    path(
        "request-password-reset/",
        RequestPasswordResetView.as_view(),
        name="request-password-reset",
    ),
    path(
        "confirm-password-reset/",
        ConfirmPasswordResetView.as_view(),
        name="confirm-password-reset",
    ),
    path("user-timesheets/", UserTimesheetListView.as_view(), name="user-timesheets"),
    path(
        "validate-multiple-timesheets/",
        ValidateMultipleTimesheetView.as_view(),
        name="validate-multiple-timesheets",
    ),
    path("push-email/", PushTimesheetEmailView.as_view(), name="push-email"),
    path(
        "project-user-roles/", ProjectUserRolesView.as_view(), name="project-user-roles"
    ),
    path(
        "project-user-roles/<int:project_id>/", ProjectUsersView.as_view(), name="project-users"
    ),
]
