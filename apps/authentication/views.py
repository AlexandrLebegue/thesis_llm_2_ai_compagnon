from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.sessions.models import Session
from django.contrib.auth import get_user_model
from django_htmx.http import HttpResponseClientRedirect
import json
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class AuthModalView(TemplateView):
    """Display the authentication modal"""
    template_name = 'authentication/auth_modal.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['show_modal'] = not self.request.user.is_authenticated
        return context


class LoginView(View):
    """Handle user login via HTMX"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            email = data.get('email')
            password = data.get('password')
            remember_me = data.get('remember_me', False)
            
            if not email or not password:
                return JsonResponse({
                    'success': False,
                    'error': 'Email and password are required'
                }, status=400)
            
            # Try to authenticate user
            user = authenticate(request, username=email, password=password)
            
            if user and user.is_active:
                login(request, user)
                
                # Handle remember me
                if not remember_me:
                    request.session.set_expiry(0)  # Browser session only
                
                # Convert guest data if user was a guest
                if hasattr(user, 'is_guest') and user.is_guest:
                    user.convert_from_guest()
                
                return JsonResponse({
                    'success': True,
                    'redirect_url': '/',
                    'message': f'Welcome back, {user.display_name}!'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid email or password'
                }, status=400)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid request format'
            }, status=400)
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'An error occurred during login'
            }, status=500)


class RegisterView(View):
    """Handle user registration via HTMX"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            email = data.get('email')
            password = data.get('password')
            password_confirm = data.get('password_confirm')
            first_name = data.get('first_name', '')
            last_name = data.get('last_name', '')
            
            # Validation
            if not email or not password:
                return JsonResponse({
                    'success': False,
                    'error': 'Email and password are required'
                }, status=400)
            
            if password != password_confirm:
                return JsonResponse({
                    'success': False,
                    'error': 'Passwords do not match'
                }, status=400)
            
            if len(password) < 8:
                return JsonResponse({
                    'success': False,
                    'error': 'Password must be at least 8 characters long'
                }, status=400)
            
            # Check if user already exists
            if User.objects.filter(email=email).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'An account with this email already exists'
                }, status=400)
            
            # Create user
            user = User.objects.create_user(
                username=email,  # Use email as username
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                is_guest=False
            )
            
            # Log user in
            login(request, user)
            
            return JsonResponse({
                'success': True,
                'redirect_url': '/',
                'message': f'Welcome, {user.display_name}! Your account has been created.'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid request format'
            }, status=400)
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'An error occurred during registration'
            }, status=500)


class GuestLoginView(View):
    """Handle guest mode login"""
    
    def post(self, request):
        try:
            # Create or get guest user for this session
            session_key = request.session.session_key
            if not session_key:
                request.session.create()
                session_key = request.session.session_key
            
            # Check if guest user already exists for this session
            guest_username = f"guest_{session_key[:8]}"
            
            try:
                user = User.objects.get(username=guest_username, is_guest=True)
            except User.DoesNotExist:
                # Create new guest user
                user = User.create_guest_user(session_key)
            
            # Log in the guest user
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            
            return JsonResponse({
                'success': True,
                'redirect_url': '/',
                'message': 'Continuing as guest. Your data will only be saved for this session.',
                'is_guest': True
            })
            
        except Exception as e:
            logger.error(f"Guest login error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'An error occurred while setting up guest access'
            }, status=500)


class LogoutView(View):
    """Handle user logout"""
    
    def post(self, request):
        try:
            was_guest = hasattr(request.user, 'is_guest') and request.user.is_guest
            logout(request)
            
            message = 'You have been logged out.'
            if was_guest:
                message = 'Guest session ended. Your data has been cleared.'
            
            return JsonResponse({
                'success': True,
                'redirect_url': '/',
                'message': message
            })
            
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'An error occurred during logout'
            }, status=500)


class ProfileView(LoginRequiredMixin, TemplateView):
    """User profile management"""
    template_name = 'authentication/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        return context


class ConvertGuestView(View):
    """Convert guest account to full account"""
    
    def post(self, request):
        try:
            if not request.user.is_authenticated:
                return JsonResponse({
                    'success': False,
                    'error': 'Not authenticated'
                }, status=401)
            
            if not hasattr(request.user, 'is_guest') or not request.user.is_guest:
                return JsonResponse({
                    'success': False,
                    'error': 'User is not a guest'
                }, status=400)
            
            data = json.loads(request.body)
            email = data.get('email')
            password = data.get('password')
            first_name = data.get('first_name', '')
            last_name = data.get('last_name', '')
            
            if not email or not password:
                return JsonResponse({
                    'success': False,
                    'error': 'Email and password are required'
                }, status=400)
            
            # Check if email is already taken
            if User.objects.filter(email=email).exclude(id=request.user.id).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'An account with this email already exists'
                }, status=400)
            
            # Convert guest to full user
            user = request.user
            success = user.convert_from_guest(
                email=email,
                first_name=first_name,
                last_name=last_name
            )
            
            if success:
                user.set_password(password)
                user.save()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Your account has been upgraded! Your data is now permanently saved.',
                    'redirect_url': '/'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Failed to convert account'
                }, status=500)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid request format'
            }, status=400)
        except Exception as e:
            logger.error(f"Account conversion error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'An error occurred during account conversion'
            }, status=500)