from django.contrib import admin
from .models import (
    User,
    AnonymousProfile,
    Category,
    Post,
    Reply,
    Report,
    ModerationAction,
    FilterRule,
)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'role', 'account_status', 'created_at')
    list_filter = ('role', 'account_status')
    search_fields = ('email',)


@admin.register(AnonymousProfile)
class AnonymousProfileAdmin(admin.ModelAdmin):
    list_display = ('anonymous_name', 'user', 'created_at')
    search_fields = ('anonymous_name',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'status', 'created_at')
    list_filter = ('category', 'status')
    search_fields = ('title', 'content')


@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ('post', 'author', 'status', 'created_at')
    list_filter = ('status',)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('reporter', 'post', 'reply', 'status', 'created_at')
    list_filter = ('status',)


@admin.register(ModerationAction)
class ModerationActionAdmin(admin.ModelAdmin):
    list_display = ('moderator', 'action_type', 'post', 'reply', 'created_at')
    list_filter = ('action_type',)


@admin.register(FilterRule)
class FilterRuleAdmin(admin.ModelAdmin):
    list_display = ('keyword', 'category', 'is_active', 'created_at')
    list_filter = ('category', 'is_active')