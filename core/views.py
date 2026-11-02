from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from core.toxicity import load_toxicity_model
from django.urls import reverse
from django.db import transaction, IntegrityError
from django.contrib.auth.hashers import make_password
from django.http import HttpResponseForbidden, request
from .models import (
    User,
    AnonymousProfile,
    Category,
    Post,
    Reply,
    Report,
    ModerationAction,
)
import random


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

        def signup_error(message):
            return render(request, 'core/signup.html', {
                'error': message,
                'available_names': get_available_anonymous_names(),
            })

        if not email or not password or not confirm_password:
            return signup_error('Please fill in all required fields.')

        if password != confirm_password:
            return signup_error('Passwords do not match.')

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
                    account_status='active'
                )

                AnonymousProfile.objects.create(
                    user=user,
                    anonymous_name=anonymous_name
                )

        except IntegrityError:
            return signup_error(
                'That email or nickname is no longer available. '
                'Please try again.'
            )

        login(request, user)
        return redirect('dashboard')

    return render(request, 'core/signup.html', {
        'available_names': available_names,
    })



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
            if user.role == 'admin':
                return redirect('moderation_dashboard')

            elif user.role == 'moderator':
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

    categories = Category.objects.all()

    return render(request, 'core/dashboard.html', {
        'categories': categories
    })

    return render(request, 'core/dashboard.html')


def create_post(request):
    if not request.user.is_authenticated:
        return redirect('login')

    categories = Category.objects.all()
    selected_category_id = request.GET.get('category')

    if request.method == 'POST':
        category_id = request.POST.get('category')
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()

        def show_error(message):
            return render(request, 'core/create_post.html', {
                'categories': categories,
                'selected_category_id': category_id,
                'error': message
            })

        if not category_id or not title or not content:
            return show_error('Please fill in all fields.')

        if len(title) > 200:
            return show_error('The title cannot exceed 200 characters.')

        if len(content) > 2000:
            return show_error('Your post cannot exceed 2,000 characters.')

        category = Category.objects.filter(
            category_id=category_id
        ).first()

        if category is None:
            return show_error('Please select a valid category.')

        try:
            model = load_toxicity_model()
            prediction = int(model.predict([f"{title} {content}"])[0])
        except Exception:
            return show_error(
                'We could not check your post right now. Please try again later.'
            )

        anonymous_profile = request.user.anonymousprofile

        Post.objects.create(
            author=anonymous_profile,
            category=category,
            title=title,
            content=content,
            status='flagged' if prediction == 1 else 'active'
        )

        if prediction == 1:
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
        'selected_category_id': selected_category_id
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

            if reply_error:
                reply_error_post_id = str(post.post_id)
            else:
                Reply.objects.create(
                    post=post,
                    author=request.user.anonymousprofile,
                    content=content
                )

                messages.success(request, 'Your reply has been posted.')

                return redirect(
                    f"{reverse('category_posts', args=[category_id])}"
                    f"?page={page_number}#post-{post.post_id}"
                )

    posts_list = Post.objects.filter(
        category=category,
        status='active'
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



def moderation_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if not (
        request.user.is_superuser
        or request.user.role in ['admin', 'moderator']
    ):
        return HttpResponseForbidden(
            'You are not authorized to access this page.'
        )

    # Handle moderation actions
    if request.method == 'POST':
        action = request.POST.get('action')
        notes = request.POST.get('notes', '').strip()

        # AI-flagged posts
        ai_post_id = request.POST.get('ai_post_id')
        print("AI POST ID:", ai_post_id)
        print("POST DATA:", request.POST)

        if ai_post_id:
            post = Post.objects.filter(
                pk=ai_post_id,
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

            ModerationAction.objects.create(
                moderator=request.user,
                post=post,
                action_type=action,
                reason=notes or f'AI-flagged post {action}d by moderator.',
            )

            messages.success(request, success_message)
            return redirect('/moderation-dashboard/?status=ai_flagged')

        # User-reported content
        report_id = request.POST.get('report_id')

        report = Report.objects.filter(
            pk=report_id
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

        report.save(update_fields=['status'])

        ModerationAction.objects.create(
            moderator=request.user,
            post=report.post,
            reply=report.reply,
            action_type=action,
            reason=notes or f'Report {action} by moderator.',
        )

        messages.success(
            request,
            'Moderation action completed successfully.'
        )

        return redirect('moderation_dashboard')

    # Report counts
    pending_count = Report.objects.filter(status='pending').count()
    resolved_count = Report.objects.filter(status='resolved').count()
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

    ai_flagged_count = all_ai_flagged_posts.count()

    selected_filter = request.GET.get('status', 'overview')

    valid_filters = [
        'overview',
        'pending',
        'resolved',
        'dismissed',
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

    if selected_filter in ['pending', 'resolved', 'dismissed']:
        reports = reports.filter(status=selected_filter)
    else:
        reports = reports.none()

    ai_flagged_posts = (
        all_ai_flagged_posts
        if selected_filter == 'ai_flagged'
        else Post.objects.none()
    )

    context = {
        'reports': reports,
        'pending_count': pending_count,
        'resolved_count': resolved_count,
        'dismissed_count': dismissed_count,
        'removed_count': removed_count,
        'removed_posts': removed_posts,
        'removed_replies': removed_replies,
        'ai_flagged_posts': ai_flagged_posts,
        'ai_flagged_count': ai_flagged_count,
        'selected_filter': selected_filter,
    }

    return render(
        request,
        'core/moderation_dashboard.html',
        context
    )


def moderation_report_detail(request, report_id):
    if not request.user.is_authenticated:
        return redirect('login')

    if not (
        request.user.is_superuser
        or request.user.role in ['admin', 'moderator']
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
