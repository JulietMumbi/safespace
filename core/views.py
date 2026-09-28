from django.http import request
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from .models import User, AnonymousProfile, Category, Post
import random


def home(request):
    return render(request, 'core/home.html')


def generate_anonymous_name():
    adjectives = [
        'Quiet',
        'Brave',
        'Calm',
        'Kind',
        'Gentle',
        'Hopeful',
        'Peaceful',
        'Bright',
        'Strong',
        'Caring'
    ]

    nouns = [
        'Moon',
        'Star',
        'Cloud',
        'River',
        'Sun',
        'Sky',
        'Leaf',
        'Light',
        'Breeze',
        'Dawn'
    ]

    while True:
        name = (
            f"{random.choice(adjectives)}"
            f"{random.choice(nouns)}"
            f"{random.randint(10, 99)}"
        )

        if not AnonymousProfile.objects.filter(
            anonymous_name=name
        ).exists():
            return name


def signup(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if not email or not password or not confirm_password:
            return render(request, 'core/signup.html', {
                'error': 'Please fill in all fields.'
            })

        if password != confirm_password:
            return render(request, 'core/signup.html', {
                'error': 'Passwords do not match.'
            })

        if User.objects.filter(email=email).exists():
            return render(request, 'core/signup.html', {
                'error': 'An account with this email already exists.'
            })

        user = User.objects.create(
            email=email,
            password=make_password(password),
            role='student',
            account_status='active'
        )

        anonymous_name = generate_anonymous_name()

        AnonymousProfile.objects.create(
            user=user,
            anonymous_name=anonymous_name
        )

        login(request, user)

        return redirect('dashboard')

    return render(request, 'core/signup.html')


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

        if not category_id or not title or not content:
            return render(request, 'core/create_post.html', {
                'categories': categories,
                'selected_category_id': category_id,
                'error': 'Please fill in all fields.'
            })

        category = Category.objects.get(category_id=category_id)

        anonymous_profile = request.user.anonymousprofile

        Post.objects.create(
            author=anonymous_profile,
            category=category,
            title=title,
            content=content
        )

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

    category = Category.objects.get(category_id=category_id)

    posts = Post.objects.filter(
        category=category,
        status='active'
    ).order_by('-created_at')

    return render(request, 'core/category_posts.html', {
        'category': category,
        'posts': posts
    })