from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Count, Q, Max, Min, Prefetch
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.urls import reverse
from .toxicity import contains_self_harm_concern
from .toxicity import load_toxicity_model, contains_disguised_abuse
from django.db import transaction, IntegrityError
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import make_password
from datetime import timedelta
from django.db.models.functions import TruncDate, TruncMonth
from .models import AccountViolation
from django.http import HttpResponseForbidden
from collections import defaultdict
from django.core.exceptions import PermissionDenied
from .models import (
    User,
    AnonymousProfile,
    Category,
    Post,
    Reply,
    Report,
    ModerationAction,
    AccountViolation,
    AccountModerationAction,
)
import random
import re


def home(request):
    return render(request, 'core/home.html')



def generate_anonymous_name():
    adjectives = [
        'Quiet', 'Brave', 'Calm', 'Kind', 'Gentle',
        'Hopeful', 'Peaceful', 'Bright', 'Strong', 'Caring'
    ]

    nouns = [
        'Moon', 'Star', 'Cloud', 'River', 'Sun',
        'Sky', 'Leaf', 'Light', 'Breeze', 'Dawn'
    ]

    # Try random combinations first
    for _ in range(100):
        name = (
            f"{random.choice(adjectives)}"
            f"{random.choice(nouns)}"
            f"{random.randint(10, 99)}"
        )

        if not AnonymousProfile.objects.filter(
            anonymous_name__iexact=name
        ).exists():
            return name

    # Check every combination if random attempts fail
    for adjective in adjectives:
        for noun in nouns:
            for number in range(10, 100):
                name = f"{adjective}{noun}{number}"

                if not AnonymousProfile.objects.filter(
                    anonymous_name__iexact=name
                ).exists():
                    return name

    raise ValueError(
        "No anonymous nicknames are currently available."
    )




def get_available_anonymous_names(limit=20):
    names = []
    selected_names = set()
    attempts = 0

    while len(names) < limit and attempts < limit * 20:
        try:
            name = generate_anonymous_name()
        except ValueError:
            break

        attempts += 1

        if name.lower() not in selected_names:
            names.append(name)
            selected_names.add(name.lower())

    return names






def signup(request):
    available_names = get_available_anonymous_names()

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        anonymous_name = request.POST.get('anonymous_name', '').strip()
        consent = request.POST.get('community_guidelines_accepted')

        def signup_error(message):
            return render(request, 'core/signup.html', {
                'error': message,
                'available_names': get_available_anonymous_names(),
            })

        if not email or not password or not confirm_password:
            return signup_error('Please fill in all required fields.')

        if consent != 'yes':
            return signup_error(
                'You must read and agree to the Community Guidelines before registering.'
            )

        if password != confirm_password:
            return signup_error('Passwords do not match.')

        try:
            validate_password(password, user=User(email=email))
        except ValidationError as error:
            return signup_error(' '.join(error.messages))

        if len(password) < 8:
            return signup_error(
                'Password must contain at least 8 characters.'
            )

        if not re.search(r'[A-Z]', password):
            return signup_error(
                'Password must contain at least one uppercase letter.'
            )

        if not re.search(r'[a-z]', password):
            return signup_error(
                'Password must contain at least one lowercase letter.'
            )

        if not re.search(r'\d', password):
            return signup_error(
                'Password must contain at least one number.'
            )

        if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/~`]', password):
            return signup_error(
                'Password must contain at least one special character.'
            )

        if User.objects.filter(email=email).exists():
            return signup_error(
                'An account with this email already exists.'
            )

        try:
            with transaction.atomic():
                if anonymous_name and AnonymousProfile.objects.filter(
                    anonymous_name__iexact=anonymous_name
                ).exists():
                    return signup_error(
                        'That nickname is already taken. Please choose another.'
                    )

                if not anonymous_name:
                    anonymous_name = generate_anonymous_name()

                user = User.objects.create(
                    email=email,
                    password=make_password(password),
                    role='student',
                    account_status='active',
                    community_guidelines_accepted=True,
                    consent_accepted_at=timezone.now()
                )

                AnonymousProfile.objects.create(
                    user=user,
                    anonymous_name=anonymous_name
                )

        except IntegrityError:
            return signup_error(
                'That email or nickname is no longer available. Please try again.'
            )

        login(request, user)
        return redirect('dashboard')

    return render(request, 'core/signup.html', {
        'available_names': available_names,
    })

def community_guidelines(request):
    return render(request, 'core/community_guidelines.html')


def user_login(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(
            request,
            email=email,
            password=password
        )

        if user is not None:

            if user.account_status != 'active':
                return render(request, 'core/login.html', {
                    'error': 'Your account is not currently active.'
                })

            login(request, user)

            # Redirect users according to their roles
            # Redirect users according to their roles
            if user.role == 'moderator':
                return redirect('moderation_dashboard')

            else:
                return redirect('dashboard')

        return render(request, 'core/login.html', {
            'error': 'Invalid email or password.'
        })

    return render(request, 'core/login.html')




def user_logout(request):
    logout(request)
    return redirect('home')


def dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')

    # Allow students to acknowledge their warnings.
    if request.method == 'POST':
        warning_id = request.POST.get('acknowledge_warning_id')

        if warning_id and warning_id.isdigit():
            warning = AccountModerationAction.objects.filter(
                pk=int(warning_id),
                target_user=request.user,
                action_type='warning',
                acknowledged_at__isnull=True
            ).first()

            if warning:
                warning.acknowledged_at = timezone.now()
                warning.save(update_fields=['acknowledged_at'])

                messages.success(
                    request,
                    'Your acknowledgement has been recorded.'
                )

        return redirect('dashboard')

    categories = Category.objects.all()

    confirmed_violation_count = AccountViolation.objects.filter(
        user=request.user
    ).count()

    account_at_risk = (
        confirmed_violation_count >= AT_RISK_THRESHOLD
    )

    account_warning_actions = AccountModerationAction.objects.filter(
        target_user=request.user,
        action_type='warning',
        acknowledged_at__isnull=True
    ).order_by('-created_at')

    return render(request, 'core/dashboard.html', {
        'categories': categories,
        'confirmed_violation_count': confirmed_violation_count,
        'account_at_risk': account_at_risk,
        'account_warning_actions': account_warning_actions,
    })






def create_post(request):
    if not request.user.is_authenticated:
        return redirect('login')

    categories = Category.objects.all()
    selected_category_id = request.GET.get('category')

    if request.method == 'POST':
        category_id = request.POST.get('category')
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        emotional_state = request.POST.get('emotional_state', '').strip()

        def show_error(message):
            return render(request, 'core/create_post.html', {
                'categories': categories,
                'selected_category_id': category_id,
                'selected_emotional_state': emotional_state,
                'emotional_state_choices': Post.EMOTIONAL_STATE_CHOICES,
                'entered_title': title,
                'entered_content': content,
                'error': message
            })

        if not category_id or not title or not content:
            return show_error('Please fill in all required fields.')

        if len(title) > 200:
            return show_error('The title cannot exceed 200 characters.')

        if len(content) > 2000:
            return show_error('Your post cannot exceed 2,000 characters.')

        valid_emotional_states = dict(Post.EMOTIONAL_STATE_CHOICES)

        if emotional_state and emotional_state not in valid_emotional_states:
            return show_error('Please select a valid emotional state.')

        category = Category.objects.filter(
            category_id=category_id
        ).first()

        if category is None:
            return show_error('Please select a valid category.')

        text_to_check = f"{title} {content}"

        # Check for disguised abusive words.
        disguised_abuse = contains_disguised_abuse(text_to_check)

        try:
            # Run the existing AI model.
            model = load_toxicity_model()
            prediction = int(model.predict([text_to_check])[0])

        except Exception:
            return show_error(
                'We could not check your post right now. Please try again later.'
            )

        # Check for self-harm concerns.
        self_harm_concern = contains_self_harm_concern(text_to_check)

        # Flag the post if any check detects a concern.
        should_flag = (
            disguised_abuse
            or self_harm_concern
            or prediction == 1
        )

        anonymous_profile = request.user.anonymousprofile

        Post.objects.create(
            author=anonymous_profile,
            category=category,
            title=title,
            content=content,
            emotional_state=emotional_state or None,
            status='flagged' if should_flag else 'active'
        )

        if should_flag:
            messages.info(
                request,
                'Your post was submitted for moderator review.'
            )
        else:
            messages.success(
                request,
                'Post submitted successfully! Your post has been shared anonymously.'
            )

        return redirect('dashboard')

    return render(request, 'core/create_post.html', {
        'categories': categories,
        'selected_category_id': selected_category_id,
        'emotional_state_choices': Post.EMOTIONAL_STATE_CHOICES,
        'selected_emotional_state': '',
        'entered_title': '',
        'entered_content': ''
    })


def category_posts(request, category_id):
    if not request.user.is_authenticated:
        return redirect('login')

    category = Category.objects.filter(
        category_id=category_id
    ).first()

    if category is None:
        return redirect('dashboard')

    reply_error = None
    reply_error_post_id = None

    if request.method == 'POST':
        action = request.POST.get('action')

        # REPORT A POST OR REPLY
        if action == 'report':
            target_type = request.POST.get('target_type')
            target_id = request.POST.get('target_id')
            reason = request.POST.get('reason', '').strip()

            valid_reasons = [
                'Harassment or bullying',
                'Hate speech',
                'Abuse or threats',
                'Self-harm or suicide concern',
                'Spam or irrelevant content',
                'Other',
            ]

            if reason not in valid_reasons:
                messages.error(request, 'Please select a valid report reason.')
                return redirect(
                    reverse('category_posts', args=[category_id])
                )

            post = None
            reply = None

            if target_type == 'post':
                post = Post.objects.filter(
                    post_id=target_id,
                    category=category,
                    status='active'
                ).first()

            elif target_type == 'reply':
                reply = Reply.objects.filter(
                    pk=target_id,
                    post__category=category,
                    status='active',
                    post__status='active'
                ).first()

            if post is None and reply is None:
                messages.error(
                    request,
                    'This content is no longer available to report.'
                )
                return redirect(
                    reverse('category_posts', args=[category_id])
                )

            existing_report = Report.objects.filter(
                reporter=request.user,
                status='pending',
            )

            if post is not None:
                already_reported = existing_report.filter(
                    post=post,
                    reply__isnull=True
                ).exists()
            else:
                already_reported = existing_report.filter(
                    reply=reply,
                    post__isnull=True
                ).exists()

            if already_reported:
                messages.info(
                    request,
                    'You have already reported this content. '
                    'Your report is awaiting review.'
                )
            else:
                Report.objects.create(
                    reporter=request.user,
                    post=post,
                    reply=reply,
                    reason=reason,
                )

                messages.success(
                    request,
                    'Report submitted. Thank you for helping keep SafeSpace safe.'
                )

            anchor_id = (
                post.post_id if post is not None
                else reply.post.post_id
            )

            return redirect(
                f"{reverse('category_posts', args=[category_id])}"
                f"#post-{anchor_id}"
            )

        # SUBMIT A REPLY
        if action == 'reply':
            post_id = request.POST.get('post_id')
            content = request.POST.get('reply_content', '').strip()
            page_number = request.POST.get('page', '1')

            post = Post.objects.filter(
                post_id=post_id,
                category=category,
                status='active'
            ).first()

            if post is None:
                messages.error(
                    request,
                    'This discussion is no longer available.'
                )
                return redirect(
                    reverse('category_posts', args=[category_id])
                )

            if not content:
                reply_error = 'Please write something before submitting.'

            elif len(content) > 1000:
                reply_error = 'Your reply cannot exceed 1,000 characters.'

            else:
                # Check for disguised abusive words.
                disguised_abuse = contains_disguised_abuse(content)

                try:
                    # Run the existing AI model.
                    model = load_toxicity_model()
                    prediction = int(model.predict([content])[0])

                except Exception:
                    reply_error = (
                        'We could not check your reply right now. '
                        'Please try again later.'
                    )

                else:
                    # Flag the reply if either check detects a concern.
                    should_flag = disguised_abuse or prediction == 1

                    Reply.objects.create(
                        post=post,
                        author=request.user.anonymousprofile,
                        content=content,
                        status='flagged' if should_flag else 'active'
                    )

                    if should_flag:
                        messages.info(
                            request,
                            'Your reply was submitted for moderator review.'
                        )
                    else:
                        messages.success(
                            request,
                            'Your reply has been posted.'
                        )

                    return redirect(
                        f"{reverse('category_posts', args=[category_id])}"
                        f"?page={page_number}#post-{post.post_id}"
                    )

            if reply_error:
                reply_error_post_id = str(post.post_id)

    posts_list = Post.objects.filter(
        category=category,
        status='active'
    ).annotate(
        active_reply_count=Count(
            'replies',
            filter=Q(replies__status='active')
        )
    ).order_by('-created_at')

    paginator = Paginator(posts_list, 10)
    page_obj = paginator.get_page(request.GET.get('page', '1'))

    return render(request, 'core/category_posts.html', {
        'category': category,
        'posts': page_obj,
        'page_obj': page_obj,
        'reply_error': reply_error,
        'reply_error_post_id': reply_error_post_id,
    })


AT_RISK_THRESHOLD = 3


def record_confirmed_violation(moderation_action, target):
    """
    Record one confirmed violation after a moderator removes content.
    AI flags and unreviewed reports are not counted.
    """

    if isinstance(target, Post):
        content_type = 'post'
        content_title = target.title
        content_excerpt = target.content

    elif isinstance(target, Reply):
        content_type = 'reply'
        content_title = target.post.title
        content_excerpt = target.content

    else:
        return

    AccountViolation.objects.get_or_create(
        moderation_action=moderation_action,
        defaults={
            'user': target.author.user,
            'content_type': content_type,
            'content_title': content_title,
            'content_excerpt': content_excerpt,
            'reason': (
                moderation_action.reason
                or 'Content removed by a moderator.'
            ),
        }
    )


def moderation_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if not (
        request.user.is_superuser
        or request.user.role in ['moderator']
    ):
        return HttpResponseForbidden(
            'You are not authorized to access this page.'
        )

    # Handle moderation actions
    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('notes', '').strip()

        # AI-FLAGGED REPLIES
        ai_reply_id = (request.POST.get('ai_reply_id') or '').strip()

        if ai_reply_id:
            if not ai_reply_id.isdigit():
                messages.error(request, 'Invalid reply ID.')
                return redirect('/moderation-dashboard/?status=ai_flagged')

            reply = Reply.objects.filter(
                pk=int(ai_reply_id),
                status='flagged'
            ).first()

            if reply is None:
                messages.error(
                    request,
                    'AI-flagged reply not found or already reviewed.'
                )
                return redirect('/moderation-dashboard/?status=ai_flagged')

            if action not in ['remove', 'dismiss']:
                messages.error(request, 'Invalid moderation action.')
                return redirect('/moderation-dashboard/?status=ai_flagged')

            if action == 'remove':
                reply.status = 'removed'
                success_message = 'AI-flagged reply removed successfully.'
            else:
                reply.status = 'active'
                success_message = (
                    'AI flag dismissed. The reply is now visible to students.'
                )

            reply.save(update_fields=['status'])

            moderation_action = ModerationAction.objects.create(
                moderator=request.user,
                reply=reply,
                action_type=action,
                reason=notes or f'AI-flagged reply {action}d by moderator.',
            )

            if action == 'remove':
                record_confirmed_violation(moderation_action, reply)

            messages.success(request, success_message)
            return redirect('/moderation-dashboard/?status=ai_flagged')

        # AI-FLAGGED POSTS
        ai_post_id = (request.POST.get('ai_post_id') or '').strip()

        if ai_post_id:
            if not ai_post_id.isdigit():
                messages.error(request, 'Invalid post ID.')
                return redirect('/moderation-dashboard/?status=ai_flagged')

            post = Post.objects.filter(
                pk=int(ai_post_id),
                status='flagged'
            ).first()

            if post is None:
                messages.error(
                    request,
                    'AI-flagged post not found or already reviewed.'
                )
                return redirect('/moderation-dashboard/?status=ai_flagged')

            if action not in ['remove', 'dismiss']:
                messages.error(request, 'Invalid moderation action.')
                return redirect('/moderation-dashboard/?status=ai_flagged')

            if action == 'remove':
                post.status = 'removed'
                success_message = 'AI-flagged post removed successfully.'
            else:
                post.status = 'active'
                success_message = 'AI flag dismissed. The post is now active.'

            post.save(update_fields=['status'])

            moderation_action = ModerationAction.objects.create(
                moderator=request.user,
                post=post,
                action_type=action,
                reason=notes or f'AI-flagged post {action}d by moderator.',
            )

            if action == 'remove':
                record_confirmed_violation(moderation_action, post)

            messages.success(request, success_message)
            return redirect('/moderation-dashboard/?status=ai_flagged')

        # USER-REPORTED CONTENT
        report_id = (request.POST.get('report_id') or '').strip()

        if not report_id.isdigit():
            messages.error(request, 'Invalid report ID. Please try again.')
            return redirect('moderation_dashboard')

        report = Report.objects.filter(
            pk=int(report_id)
        ).select_related('post', 'reply').first()

        if report is None:
            messages.error(request, 'Report not found.')
            return redirect('moderation_dashboard')

        if report.status != 'pending':
            messages.error(
                request,
                'This report has already been reviewed.'
            )
            return redirect(
                'moderation_report_detail',
                report_id=report.pk
            )

        if action not in ['remove', 'dismiss']:
            messages.error(request, 'Invalid moderation action.')
            return redirect(
                'moderation_report_detail',
                report_id=report.pk
            )

        if action == 'remove':
            target = report.post if report.post_id else report.reply

            if target is None:
                messages.error(
                    request,
                    'The reported content is no longer available.'
                )
                return redirect(
                    'moderation_report_detail',
                    report_id=report.pk
                )

            target.status = 'removed'
            target.save(update_fields=['status'])
            report.status = 'resolved'

        elif action == 'dismiss':
            report.status = 'dismissed'

        report.reviewed_at = timezone.now()
        report.reviewed_by = request.user
        report.moderator_notes = notes

        report.save(update_fields=[
    'status',
    'reviewed_at',
    'reviewed_by',
    'moderator_notes',
])

        moderation_action = ModerationAction.objects.create(
            moderator=request.user,
            post=report.post,
            reply=report.reply,
            action_type=action,
            reason=notes or f'Report {action} by moderator.',
        )

        if action == 'remove':
            record_confirmed_violation(moderation_action, target)

        messages.success(
            request,
            'Moderation action completed successfully.'
        )

        return redirect('moderation_dashboard')

    # Report counts
    resolved_count = Report.objects.filter(status='resolved').count()
    pending_count = Report.objects.filter(status='pending').count()
    dismissed_count = Report.objects.filter(status='dismissed').count()

    # Removed content
    removed_posts = Post.objects.filter(
        status='removed'
    ).select_related(
        'author', 'category'
    ).order_by('-created_at')

    removed_replies = Reply.objects.filter(
        status='removed'
    ).select_related(
        'author', 'post', 'post__category'
    ).order_by('-created_at')

    removed_count = removed_posts.count() + removed_replies.count()

    # AI-flagged posts
    all_ai_flagged_posts = Post.objects.filter(
        status='flagged'
    ).select_related(
        'author', 'category'
    ).order_by('-created_at')

    ai_flagged_post_count = all_ai_flagged_posts.count()

    # AI-flagged replies
    all_ai_flagged_replies = Reply.objects.filter(
        status='flagged'
    ).select_related(
        'author', 'post', 'post__category'
    ).order_by('-created_at')

    ai_flagged_reply_count = all_ai_flagged_replies.count()

    # Combined AI-flagged count
    ai_flagged_count = (
        ai_flagged_post_count + ai_flagged_reply_count
    )
        # COMMUNITY INSIGHTS

    # Count only active posts and their active replies.
    # Removed and AI-flagged content is excluded.
    active_posts_with_replies = Post.objects.filter(
        status='active'
    ).annotate(
        active_reply_count=Count(
            'replies',
            filter=Q(replies__status='active'),
            distinct=True
        )
    )

    total_active_posts = active_posts_with_replies.count()

    # Active posts with no active replies.
    unanswered_posts = active_posts_with_replies.filter(
        active_reply_count=0
    )

    unanswered_posts_count = unanswered_posts.count()

    unanswered_rate = (
        round((unanswered_posts_count / total_active_posts) * 100, 1)
        if total_active_posts > 0 else 0
    )

    # Unanswered posts grouped by category.
    category_unanswered_insights = []

    for category in Category.objects.all().order_by('name'):

        category_posts = active_posts_with_replies.filter(
            category=category
        )

        category_total = category_posts.count()

        if category_total == 0:
            continue

        category_unanswered_count = category_posts.filter(
            active_reply_count=0
        ).count()

        category_unanswered_insights.append({
            'name': category.name,
            'total_posts': category_total,
            'unanswered_count': category_unanswered_count,
        })

    # Sort categories from the most unanswered posts to the least.
    category_unanswered_insights.sort(
        key=lambda item: item['unanswered_count'],
        reverse=True
    )

    # Calculate bar widths for the category chart.
    highest_unanswered_count = max(
        [item['unanswered_count'] for item in category_unanswered_insights],
        default=0
    )

    for item in category_unanswered_insights:
        item['bar_width'] = (
            round(
                item['unanswered_count'] / highest_unanswered_count * 100
            )
            if highest_unanswered_count > 0 else 0
        )

    selected_filter = request.GET.get('status', 'overview')

    valid_filters = [
        'overview',
        'pending',
        'dismissed',
        'resolved',
        'removed',
        'ai_flagged',
    ]

    if selected_filter not in valid_filters:
        selected_filter = 'overview'

    reports = Report.objects.select_related(
        'reporter',
        'post',
        'reply',
        'post__author',
        'post__category',
        'reply__author',
        'reply__post',
    ).order_by('-created_at')

    if selected_filter in ['pending', 'dismissed', 'resolved']:
        reports = reports.filter(status=selected_filter)
    else:
        reports = reports.none()

    # Only display AI-flagged content on the AI review page
    ai_flagged_posts = (
        all_ai_flagged_posts
        if selected_filter == 'ai_flagged'
        else Post.objects.none()
    )

    ai_flagged_replies = (
        all_ai_flagged_replies
        if selected_filter == 'ai_flagged'
        else Reply.objects.none()
    )
    at_risk_count = (
    User.objects
    .filter(role='student')
    .annotate(
        violation_count=Count(
            'account_violations',
            distinct=True
        )
    )
    .filter(violation_count__gte=AT_RISK_THRESHOLD)
    .count()
)
    
    context = {
        'reports': reports,
        'pending_count': pending_count,
        'dismissed_count': dismissed_count,
        'removed_count': removed_count,
        'removed_posts': removed_posts,
        'resolved_count': resolved_count,
        'removed_replies': removed_replies,
        'ai_flagged_posts': ai_flagged_posts,
        'ai_flagged_replies': ai_flagged_replies,
        'ai_flagged_count': ai_flagged_count,
        'ai_flagged_post_count': ai_flagged_post_count,
        'ai_flagged_reply_count': ai_flagged_reply_count,
        'total_active_posts': total_active_posts,
        'unanswered_posts_count': unanswered_posts_count,
        'unanswered_rate': unanswered_rate,
        'category_unanswered_insights': category_unanswered_insights,
        'selected_filter': selected_filter,
        'at_risk_count': AccountViolation.objects.values(
            'user'
        ).annotate(
            total_violations=Count('user')
        ).filter(
            total_violations__gte=AT_RISK_THRESHOLD
        ).count(),
    }

    return render(
        request,
        'core/moderation_dashboard.html',
        context
    )
    

@login_required
def community_insights(request):
    if not (request.user.is_superuser or request.user.role == 'moderator'):
        raise PermissionDenied

    # Date filter
    period = request.GET.get('period', '30')

    if period not in ['7', '30', '90', 'all']:
        period = '30'

    now = timezone.now()
    start_date = None if period == 'all' else now - timedelta(days=int(period))

    # Reusable date filter
    def apply_period(queryset):
        if start_date:
            return queryset.filter(created_at__gte=start_date)
        return queryset

    # --------------------------------------------------
    # 1. COMMUNITY ACTIVITY: POSTS AND REPLIES OVER TIME
    # --------------------------------------------------

    posts = apply_period(Post.objects.filter(status='active'))
    replies = apply_period(Reply.objects.filter(status='active'))

    if period == 'all':
        date_function = TruncMonth
    else:
        date_function = TruncDate

    activity = defaultdict(lambda: {'posts': 0, 'replies': 0})

    post_activity = (
        posts.annotate(date_group=date_function('created_at'))
        .values('date_group')
        .annotate(total=Count('pk'))
        .order_by('date_group')
    )

    reply_activity = (
        replies.annotate(date_group=date_function('created_at'))
        .values('date_group')
        .annotate(total=Count('pk'))
        .order_by('date_group')
    )

    for item in post_activity:
        if item['date_group']:
            activity[item['date_group']]['posts'] = item['total']

    for item in reply_activity:
        if item['date_group']:
            activity[item['date_group']]['replies'] = item['total']

    sorted_dates = sorted(activity.keys())

    activity_labels = [
        date.strftime('%b %Y') if period == 'all'
        else date.strftime('%d %b')
        for date in sorted_dates
    ]

    activity_posts = [activity[date]['posts'] for date in sorted_dates]
    activity_replies = [activity[date]['replies'] for date in sorted_dates]

    # --------------------------------------------------
    # 2. CATEGORY INSIGHTS
    # --------------------------------------------------

    category_data = (
        posts.values('category__name')
        .annotate(total=Count('pk'))
        .order_by('-total')
    )

    category_labels = [
        item['category__name'] for item in category_data[:10]
    ]

    category_counts = [
        item['total'] for item in category_data[:10]
    ]

    # --------------------------------------------------
    # 3. POST ENGAGEMENT
    # Include posts that have received ZERO replies
    # --------------------------------------------------

    posts_with_reply_counts = posts.annotate(
        active_reply_count=Count(
            'replies',
            filter=Q(replies__status='active')
        )
    )

    answered_posts = posts_with_reply_counts.filter(
        active_reply_count__gt=0
    ).count()

    unanswered_posts = posts_with_reply_counts.filter(
        active_reply_count=0
    ).count()

    # --------------------------------------------------
    # 4. EMOTIONAL WELLBEING TRENDS
    # --------------------------------------------------

    emotional_data = (
        posts.exclude(emotional_state__isnull=True)
        .exclude(emotional_state='')
        .values('emotional_state')
        .annotate(total=Count('pk'))
        .order_by('-total')
    )

    emotional_choices = dict(Post.EMOTIONAL_STATE_CHOICES)

    emotional_labels = [
        emotional_choices.get(item['emotional_state'],
                              item['emotional_state'])
        for item in emotional_data
    ]

    emotional_counts = [
        item['total'] for item in emotional_data
    ]

    # --------------------------------------------------
    # 5. MODERATION INSIGHTS
    # --------------------------------------------------

    flagged_posts = apply_period(
        Post.objects.filter(status='flagged')
    ).count()

    flagged_replies = apply_period(
        Reply.objects.filter(status='flagged')
    ).count()

    removed_posts = apply_period(
        Post.objects.filter(status='removed')
    ).count()

    removed_replies = apply_period(
        Reply.objects.filter(status='removed')
    ).count()

    pending_reports = Report.objects.filter(
        status='pending'
    ).count()

    confirmed_violations = apply_period(
        AccountViolation.objects.all()
    ).count()

    moderation_labels = [
        'AI-flagged posts',
        'AI-flagged replies',
        'Removed posts',
        'Removed replies',
        'Pending reports',
        'Confirmed violations',
    ]

    moderation_counts = [
        flagged_posts,
        flagged_replies,
        removed_posts,
        removed_replies,
        pending_reports,
        confirmed_violations,
    ]

    
    # --------------------------------------------------
    # PREPARE CSS VISUALIZATION DATA
    # --------------------------------------------------

    activity_rows = [
        {
            'label': date.strftime('%b %Y') if period == 'all'
                     else date.strftime('%d %b'),
            'posts': activity[date]['posts'],
            'replies': activity[date]['replies'],
        }
        for date in sorted_dates
    ]

    category_rows = [
        {
            'label': item['category__name'],
            'count': item['total'],
        }
        for item in category_data[:10]
    ]

    emotional_rows = [
        {
            'label': emotional_choices.get(
                item['emotional_state'],
                item['emotional_state']
            ),
            'count': item['total'],
        }
        for item in emotional_data
    ]

    moderation_rows = [
        {'label': label, 'count': count}
        for label, count in zip(moderation_labels, moderation_counts)
    ]

    # Maximum values keep the meter scales meaningful
    category_max = max(
        [item['count'] for item in category_rows] or [1]
    )

    emotional_max = max(
        [item['count'] for item in emotional_rows] or [1]
    )

    moderation_max = max(
        [item['count'] for item in moderation_rows] or [1]
    )

    activity_max = max(
        [max(item['posts'], item['replies']) for item in activity_rows]
        or [1]
    )

    engagement_total = answered_posts + unanswered_posts

    answered_percentage = (
        round((answered_posts / engagement_total) * 100)
        if engagement_total else 0
    )

    unanswered_percentage = (
        round((unanswered_posts / engagement_total) * 100)
        if engagement_total else 0
    )

    context = {
        'period': period,

        'activity_rows': activity_rows,
        'activity_max': activity_max,

        'category_rows': category_rows,
        'category_max': category_max,

        'emotional_rows': emotional_rows,
        'emotional_max': emotional_max,

        'moderation_rows': moderation_rows,
        'moderation_max': moderation_max,

        'answered_posts': answered_posts,
        'unanswered_posts': unanswered_posts,
        'engagement_total': engagement_total,
        'answered_percentage': answered_percentage,
        'unanswered_percentage': unanswered_percentage,
    }

    return render(
        request,
        'core/community_insights.html',
        context
    )



def moderation_report_detail(request, report_id):
    if not request.user.is_authenticated:
        return redirect('login')

    if not (
        request.user.is_superuser
        or request.user.role in [ 'moderator']
    ):
        return HttpResponseForbidden(
            'You are not authorized to access this page.'
        )

    report = get_object_or_404(
        Report.objects.select_related(
            'reporter',
            'post',
            'reply',
            'post__category',
            'post__author',
            'reply__author',
            'reply__post',
        ),
        pk=report_id
    )

    context = {
        'report': report,
    }

    return render(
        request,
        'core/moderation_report_detail.html',
        context
    )



def delete_post(request, post_id):
    if not request.user.is_authenticated:
        return redirect('login')

    if request.method != 'POST':
        return redirect('dashboard')

    post = get_object_or_404(
        Post,
        post_id=post_id,
        author=request.user.anonymousprofile
    )

    category_id = post.category.category_id

    post.delete()

    messages.success(
        request,
        'Your post has been deleted successfully.'
    )

    return redirect(
        reverse('category_posts', args=[category_id])
    )
    

@login_required
def my_posts(request):
    anonymous_profile = request.user.anonymousprofile

    posts = (
        Post.objects
        .filter(author=anonymous_profile)
        .exclude(status__in=['removed', 'archived'])
        .select_related('category')
        .annotate(
            reply_count=Count(
                'replies',
                filter=Q(replies__status='active')
            )
        )
        .order_by('-created_at')
    )

    replies = (
        Reply.objects
        .filter(author=anonymous_profile, status='active')
        .select_related('post', 'post__category')
        .order_by('-created_at')
    )

    posts_count = posts.count()
    replies_count = replies.count()

    return render(request, 'core/my_posts.html', {
        'posts': posts,
        'replies': replies,
        'posts_count': posts_count,
        'replies_count': replies_count,
    })


def removed_content(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if not (
        request.user.is_superuser
        or request.user.role == 'moderator'
    ):
        return HttpResponseForbidden(
            'You are not authorized to access this page.'
        )

    removed_posts = (
        Post.objects
        .filter(status='removed')
        .select_related('author', 'category')
        .annotate(
            removed_at=Max(
                'moderation_actions__created_at',
                filter=Q(moderation_actions__action_type='remove')
            )
        )
        .order_by('-removed_at', '-created_at')
    )

    removed_replies = (
        Reply.objects
        .filter(status='removed')
        .select_related('author', 'post', 'post__category')
        .annotate(
            removed_at=Max(
                'moderation_actions__created_at',
                filter=Q(moderation_actions__action_type='remove')
            )
        )
        .order_by('-removed_at', '-created_at')
    )

    # Paginate each section independently.
    posts_page = Paginator(removed_posts, 10).get_page(
        request.GET.get('posts_page', 1)
    )

    replies_page = Paginator(removed_replies, 10).get_page(
        request.GET.get('replies_page', 1)
    )

    return render(request, 'core/removed_content.html', {
        'removed_posts': posts_page,
        'removed_replies': replies_page,
        'posts_page': posts_page,
        'replies_page': replies_page,
        'removed_count': removed_posts.count() + removed_replies.count(),
    })


def account_moderation(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if not (
        request.user.is_superuser
        or request.user.role == 'moderator'
    ):
        return HttpResponseForbidden(
            'You are not authorized to access this page.'
        )

    if request.method == 'POST':
        target_user_id = request.POST.get('target_user_id')
        action = request.POST.get('action')
        notes = request.POST.get('notes', '').strip()

        target_user = get_object_or_404(
            User,
            pk=target_user_id,
            role='student',
            is_superuser=False
        )

        if target_user == request.user:
            messages.error(
                request,
                'You cannot moderate your own account.'
            )
            return redirect('account_moderation')

        valid_actions = [
            'warning',
            'suspend',
            'deactivate',
            'restore',
        ]

        if action not in valid_actions:
            messages.error(request, 'Invalid account action.')
            return redirect('account_moderation')

        if action == 'warning':
            success_message = 'Warning issued successfully.'

        elif action == 'suspend':
            target_user.account_status = 'suspended'
            target_user.save(update_fields=['account_status'])
            success_message = 'Student account suspended.'

        elif action == 'deactivate':
            target_user.account_status = 'deactivated'
            target_user.save(update_fields=['account_status'])
            success_message = 'Student account deactivated.'

        else:
            target_user.account_status = 'active'
            target_user.save(update_fields=['account_status'])
            success_message = 'Student account restored.'

        AccountModerationAction.objects.create(
            target_user=target_user,
            moderator=request.user,
            action_type=action,
            notes=notes
        )

        messages.success(request, success_message)

        return redirect('account_moderation')

    accounts = User.objects.filter(
        role='student',
        is_superuser=False,
        account_violations__isnull=False
    ).annotate(
        violation_count=Count(
            'account_violations',
            distinct=True
        )
    ).prefetch_related(
        'account_violations',
        'account_moderation_actions'
    ).order_by('-violation_count', 'email')

    at_risk_count = accounts.filter(
        account_violations__isnull=False
    ).annotate(
        total_violations=Count(
            'account_violations',
            distinct=True
        )
    ).filter(
        total_violations__gte=AT_RISK_THRESHOLD
    ).count()

    paginator = Paginator(accounts, 10)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(
        request,
        'core/account_moderation.html',
        {
            'accounts': page_obj,
            'page_obj': page_obj,
            'at_risk_count': at_risk_count,
            'risk_threshold': AT_RISK_THRESHOLD,
        }
    )
