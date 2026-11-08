
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('signup/', views.signup, name='signup'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),

    path(
        'create-post/',
        views.create_post,
        name='create_post'
    ),

    path(
        'moderation-dashboard/',
        views.moderation_dashboard,
        name='moderation_dashboard'
    ),

    path(
        'moderation-report/<int:report_id>/',
        views.moderation_report_detail,
        name='moderation_report_detail'
    ),

    path(
        'category/<int:category_id>/',
        views.category_posts,
        name='category_posts'
    ),
    
    path(
    'admin-dashboard/',
    views.admin_dashboard,
    name='admin_dashboard'
),

path(
    'admin-dashboard/restore/<int:post_id>/',
    views.restore_archived_post,
    name='restore_archived_post'
),
]
