from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    username = None

    ROLE_CHOICES = [
        ('student', 'Student'),
        ('moderator', 'Moderator'),

    ]

    ACCOUNT_STATUS_CHOICES = [
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('deactivated', 'Deactivated'),
    ]

    email = models.EmailField(unique=True)

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='student'
    )

    account_status = models.CharField(
        max_length=20,
        choices=ACCOUNT_STATUS_CHOICES,
        default='active'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    community_guidelines_accepted = models.BooleanField(default=False)

    consent_accepted_at = models.DateTimeField(
    null=True,
    blank=True
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email


class AnonymousProfile(models.Model):
    profile_id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    anonymous_name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.anonymous_name


class Category(models.Model):
    category_id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name



class Post(models.Model):

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('flagged', 'Flagged'),
        ('removed', 'Removed'),
    ]
    EMOTIONAL_STATE_CHOICES = [
    ('anxious', 'Anxious'),
    ('overwhelmed', 'Overwhelmed'),
    ('lonely', 'Lonely'),
    ('stressed', 'Stressed'),
    ('hopeful', 'Hopeful'),
    ('grateful', 'Grateful'),
    ('other', 'Other'),
]

    post_id = models.BigAutoField(primary_key=True)

    author = models.ForeignKey(
        AnonymousProfile,
        on_delete=models.CASCADE,
        related_name='posts'
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='posts'
    )

    title = models.CharField(max_length=200)
    content = models.TextField()
    emotional_state = models.CharField(
    max_length=20,
    choices=EMOTIONAL_STATE_CHOICES,
    blank=True,
    null=True
)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )


    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title




class Reply(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('flagged', 'Flagged'),
        ('removed', 'Removed'),
    ]

    reply_id = models.BigAutoField(primary_key=True)
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='replies'
    )
    author = models.ForeignKey(
        AnonymousProfile,
        on_delete=models.CASCADE,
        related_name='replies'
    )
    content = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reply to {self.post.title}"


class Report(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('reviewed', 'Reviewed'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]

    report_id = models.BigAutoField(primary_key=True)
    reporter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='reports'
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reports'
    )
    reply = models.ForeignKey(
        Reply,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reports'
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Report #{self.report_id}"


class ModerationAction(models.Model):
    ACTION_CHOICES = [
        ('flag', 'Flag'),
        ('remove', 'Remove'),
        ('dismiss', 'Dismiss'),
        ('escalate', 'Escalate'),
    ]

    action_id = models.BigAutoField(primary_key=True)
    moderator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='moderation_actions'
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='moderation_actions'
    )
    reply = models.ForeignKey(
        Reply,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='moderation_actions'
    )
    action_type = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES
    )
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Moderation Action #{self.action_id}"


class FilterRule(models.Model):
    CATEGORY_CHOICES = [
        ('self_harm', 'Self-harm'),
        ('abuse', 'Abuse'),
        ('hate_speech', 'Hate Speech'),
        ('other', 'Other'),
    ]

    rule_id = models.BigAutoField(primary_key=True)
    keyword = models.CharField(max_length=100)
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.keyword
    
    
class AccountViolation(models.Model):
    CONTENT_TYPE_CHOICES = [
        ('post', 'Post'),
        ('reply', 'Reply'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='account_violations'
    )

    moderation_action = models.OneToOneField(
        ModerationAction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='account_violation'
    )

    content_type = models.CharField(
        max_length=10,
        choices=CONTENT_TYPE_CHOICES
    )

    content_title = models.CharField(
        max_length=200,
        blank=True
    )

    content_excerpt = models.TextField()

    reason = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Violation by {self.user.email}"


class AccountModerationAction(models.Model):
    ACTION_CHOICES = [
        ('warning', 'Warning'),
        ('suspend', 'Suspend Account'),
        ('deactivate', 'Deactivate Account'),
        ('restore', 'Restore Account'),
    ]

    target_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='account_moderation_actions'
    )

    moderator = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='issued_account_actions'
    )

    action_type = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(
    null=True,
    blank=True
)

    def __str__(self):
        return f"{self.action_type} - {self.target_user.email}"
