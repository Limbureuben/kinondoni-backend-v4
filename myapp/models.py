import random
import string
from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.core.mail import send_mail
import uuid
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser


class UssdReport(models.Model):
    reference_number = models.CharField(max_length=8, unique=True, default="unknown")
    phone_number = models.CharField(max_length=255)  # Increased size to store encrypted phone number
    open_space = models.CharField(max_length=255, default='Unknown')  # Add default value here
    description = models.TextField()
    status = models.CharField(max_length=50, default='Pending')

    def __str__(self):
        return self.reference_number
    

class UserProfile(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    # user = models.OneToOneField(User, on_delete=models.CASCADE)
    verification_token = models.UUIDField(default=uuid.uuid4, editable=False)
    is_email_verified = models.BooleanField(default=False)  # Track if email is verified

    def __str__(self):
        return f"{self.user.username} Profile"

    
class ReportHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    report_id = models.CharField(max_length=8, editable=False)
    description = models.TextField()
    email = models.EmailField(blank=True, null=True)
    file = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateField(auto_now_add=True)
    
    

class Ward(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Street(models.Model):
    name = models.CharField(max_length=100)
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name='streets')

    class Meta:
        unique_together = ('name', 'ward')

    def __str__(self):
        return f"{self.name} ({self.ward.name})"


class Report(models.Model):
    report_id = models.CharField(max_length=8, unique=True, editable=False)
    description = models.TextField()
    email = models.EmailField(blank=True, null=True)
    file = models.FileField(upload_to='reports/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    space_name = models.CharField(max_length=255, blank=True, null=True)
    district = models.CharField(max_length=255, blank=True, null=True)
    street = models.CharField(max_length=255, blank=True, null=True)
    street_name_backup = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def save(self, *args, **kwargs):
        is_new = not self.pk
        if not self.report_id:
            self.report_id = self._generate_unique_id()
        super().save(*args, **kwargs)

        if is_new and self.email:
            try:
                self._send_notification_email()
            except Exception as e:
                # Optionally log the error
                print(f"Failed to send report notification: {e}")


    def _generate_unique_id(self):
        # Generate a unique 8-character ID
        unique_id = uuid.uuid4().hex[:8].upper()
        # Check if ID already exists, if so, generate a new one
        while Report.objects.filter(report_id=unique_id).exists():
            unique_id = uuid.uuid4().hex[:8].upper()
        return unique_id
    
    def _send_notification_email(self):
        subject = f'Report Received - ID: {self.report_id}'
        
        message = f'''
    ------------------------------------------------------------
    Kinondoni Environmental Report Acknowledgement
    ------------------------------------------------------------

    Your report has been successfully received.

    Report ID: {self.report_id}
    Mtaa: { self.district}
    Submission Date: {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}  
    Location: {self.space_name if self.space_name else "Not specified"}

    Thank you for taking the time to report an environmental issue.  
    Our team will review your report and take the appropriate action as soon as possible.

    Please use the Report ID above to track the progress of your report.

    ------------------------------------------------------------
    This is an automated message. Please do not reply.  
    If you need assistance, please visit our help center.

    Thank you for supporting a cleaner and safer environment.  
    Kinondoni Environmental Team
    ------------------------------------------------------------
        '''

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [self.email],
            fail_silently=False,
        )

class ReportReply(models.Model):
    report = models.ForeignKey('Report', on_delete=models.CASCADE, related_name='replies')
    message = models.TextField()
    replied_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('staff', 'Staff'),
        ('ward_executive', 'Ward Executive'),
        ('village_chairman', 'Village Chairman'),
        ('user', 'User'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)
    ward = models.ForeignKey(Ward, on_delete=models.SET_NULL, null=True, blank=True)
    street = models.ForeignKey(Street, on_delete=models.SET_NULL, null=True, blank=True)
    
    registered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='registered_users'
    )
    
    def __str__(self):
        return f"{self.username} ({self.role})"


class OpenSpace(models.Model):
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('unavailable', 'Unavailable'),
    ]
    
    name = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    district = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name='openspaces')
    street = models.ForeignKey(Street, on_delete=models.CASCADE, related_name='openspaces', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    shape_type = models.CharField(max_length=20, default='polygon')
    boundary = models.JSONField(default=dict, blank=True)
    area = models.FloatField(default=0)
    
    def __str__(self):
        return self.name

class OpenSpaceBooking(models.Model):

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]
    space = models.ForeignKey(OpenSpace, on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True)
    username = models.CharField(max_length=150)
    contact = models.CharField(max_length=20)
    startdate = models.DateField()
    enddate = models.DateField(null=True)
    purpose = models.TextField()
    district = models.CharField(max_length=250, default='Kinondoni')
    file = models.FileField(upload_to='bookings/files/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"{self.username} - {self.startdate}"
    
    
class ForwardedBooking(models.Model):
    booking = models.OneToOneField(OpenSpaceBooking, on_delete=models.CASCADE, related_name='forwarded_booking')
    ward_executive_description = models.TextField()
    
    forwarded_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    forwarded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Forwarded by {self.forwarded_by.username} - {self.booking.username} - {self.booking.date}"


class Notification(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Notification for {self.user.username}'
    
    
    
class ReportForward(models.Model):
    report = models.ForeignKey(
        'Report',
        on_delete=models.CASCADE,
        related_name='forwards'
    )
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='reports_forwarded'
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='reports_received'
    )
    forwarded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Report {self.report.report_id} from {self.from_user} to {self.to_user}"


# class ForwardedReport(models.Model):
#     report = models.ForeignKey(
#         'Report',
#         on_delete=models.CASCADE,
#         related_name='forwards'
#     )
#     forwarded_by = models.ForeignKey(
#         settings.AUTH_USER_MODEL,  # the Village Executive
#         on_delete=models.SET_NULL,
#         null=True,
#         related_name='reports_forwarded'
#     )
#     forwarded_to = models.ForeignKey(
#         settings.AUTH_USER_MODEL,  # the Ward Executive
#         on_delete=models.SET_NULL,
#         null=True,
#         related_name='reports_received'
#     )
#     forwarded_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"Report {self.report.report_id} forwarded by {self.forwarded_by} to {self.forwarded_to}"



class ReportReplyVillageExecutive(models.Model):
    report = models.ForeignKey(
        'Report',
        on_delete=models.CASCADE,
        related_name='ward_exec_replies'  # <-- unique name
    )
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_ward_exec_replies'  # also unique
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reply to {self.report.report_id} by {self.from_user.username}"


class ReportForwardToadmin(models.Model):
    report = models.ForeignKey(
        'Report',
        on_delete=models.CASCADE,
        related_name='forwards_to_admin'
    )
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='reports_forwarded_to_admin'
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='reports_received_by_admin'
    )
    message = models.TextField(blank=True, null=True)
    forwarded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Report {self.report.report_id} from {self.from_user} to {self.to_user}"
