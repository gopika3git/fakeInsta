from django.db import models
from django.utils import timezone
import uuid


# ============================================================
#                       ADMIN
# ============================================================
class AdminUser(models.Model):
    username = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=128)

    class Meta:
        db_table = 'admin_user'

    def __str__(self):
        return self.username


# ============================================================
#                       POLICE
# ============================================================
class Police(models.Model):
    full_name = models.CharField(max_length=100)
    badge_no = models.CharField(max_length=50, unique=True)
    station = models.CharField(max_length=150)
    rank = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    username = models.CharField(max_length=50, unique=True)
    password = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'police'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.badge_no} - {self.full_name}"


# ============================================================
#                       USER
# ============================================================
class RegisteredUser(models.Model):
    full_name = models.CharField(max_length=100)
    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    address = models.TextField(blank=True)
    password = models.CharField(max_length=128)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'registered_user'
        ordering = ['-created_at']

    def __str__(self):
        return self.username


# ============================================================
#                  FAKE ID VERIFICATION REQUEST
# ============================================================
class FakeIDRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
    ]
    VERDICT_CHOICES = [
        ('UNKNOWN', 'Unknown'),
        ('FAKE', 'Fake'),
        ('REAL', 'Real'),
    ]

    case_no = models.CharField(max_length=30, unique=True, editable=False)
    user = models.ForeignKey(RegisteredUser, on_delete=models.CASCADE,
                             related_name='requests')
    instagram_id = models.CharField(max_length=120)
    reason = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    verdict = models.CharField(max_length=20, choices=VERDICT_CHOICES, default='UNKNOWN')
    fake_probability = models.FloatField(null=True, blank=True)

    verified_by = models.ForeignKey(Police, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name='verifications')
    officer_notes = models.TextField(blank=True)

    raw_features = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'fake_id_request'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.case_no:
            self.case_no = 'CASE-' + uuid.uuid4().hex[:8].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.case_no} - @{self.instagram_id}"


# ============================================================
#                       COMPLAINT
# ============================================================
class Complaint(models.Model):
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('REVIEWED', 'Reviewed'),
        ('CLOSED', 'Closed'),
    ]
    user = models.ForeignKey(RegisteredUser, on_delete=models.CASCADE,
                             related_name='complaints')
    subject = models.CharField(max_length=200)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    admin_reply = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'complaint'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.subject} ({self.user.username})"


# ============================================================
#                    PREDICTION HISTORY
# ============================================================
class PredictionLog(models.Model):
    SOURCE_CHOICES = [
        ('FORM', 'Manual Form'),
        ('API', 'Apify by Instagram ID'),
    ]
    ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('POLICE', 'Police'),
        ('USER', 'User'),
    ]
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES)
    actor_role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    actor_name = models.CharField(max_length=100)
    instagram_id = models.CharField(max_length=120, blank=True)
    verdict = models.CharField(max_length=10)
    fake_probability = models.FloatField()
    features = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'prediction_log'
        ordering = ['-created_at']
