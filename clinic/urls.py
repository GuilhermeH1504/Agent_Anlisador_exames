from django.urls import path

from . import views


app_name = "clinic"

urlpatterns = [
    path("", views.index, name="index"),
    path("api/status/", views.status, name="status"),
    path("api/chat/", views.chat, name="chat"),
    path("api/patients/", views.patients, name="patients"),
    path("api/exams/", views.exams, name="exams"),
]
