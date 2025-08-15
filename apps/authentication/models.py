from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """
    Custom User model with additional fields for authentication system
    """
    is_guest = models.BooleanField(
        default=False,
        help_text="Designates whether this user is a guest user with session-only data."
    )
    
    # Additional profile fields
    profile_picture = models.URLField(
        blank=True,
        null=True,
        help_text="URL to user's profile picture from social auth"
    )
    
    # Social auth provider info
    provider = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Social authentication provider (google, github, etc.)"
    )
    
    # Data management
    data_retention_consent = models.BooleanField(
        default=True,
        help_text="User consent for data retention and processing"
    )
    
    session_converted_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When this user was converted from guest to authenticated user"
    )
    
    class Meta:
        db_table = 'auth_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        if self.is_guest:
            return f"Guest User ({self.username})"
        return self.get_full_name() or self.username
    
    @property
    def display_name(self):
        """Return the best display name for the user"""
        if self.first_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.username
    
    @property
    def is_authenticated_user(self):
        """Check if user is fully authenticated (not guest)"""
        return not self.is_guest and self.is_authenticated
    
    def convert_from_guest(self, email=None, first_name=None, last_name=None, provider=None):
        """Convert a guest user to an authenticated user"""
        if not self.is_guest:
            return False
        
        self.is_guest = False
        self.session_converted_at = timezone.now()
        
        if email:
            self.email = email
        if first_name:
            self.first_name = first_name
        if last_name:
            self.last_name = last_name
        if provider:
            self.provider = provider
            
        self.save()
        return True
    
    @classmethod
    def create_guest_user(cls, session_key):
        """Create a guest user tied to a session"""
        username = f"guest_{session_key[:8]}"
        user = cls.objects.create_user(
            username=username,
            is_guest=True,
            is_active=True
        )
        return user