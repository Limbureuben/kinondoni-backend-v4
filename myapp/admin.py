from django.contrib import admin
from .models import *


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('username', 'verification_token', 'is_email_verified')
    def username(self, obj):
        return obj.user.username
    search_fields = ('user__username', 'user__email')
admin.site.register(UserProfile, UserProfileAdmin)


class OpenSpaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'latitude', 'longitude', 'district', 'street', 'status', 'created_at', 'is_active')
admin.site.register(OpenSpace, OpenSpaceAdmin)


class ReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'report_id', 'status', 'current_level', 'priority', 'assigned_to', 'space_name', 'street', 'created_at', 'user')
    list_filter = ('status', 'current_level', 'priority')
    search_fields = ('report_id', 'description', 'space_name', 'street', 'email')
admin.site.register(Report, ReportAdmin)


@admin.register(ReportTimeline)
class ReportTimelineAdmin(admin.ModelAdmin):
    list_display = ('report', 'action', 'from_level', 'to_level', 'performed_by', 'created_at')
    list_filter = ('action', 'to_level', 'to_status')
    search_fields = ('report__report_id', 'public_comment', 'internal_comment')
    readonly_fields = (
        'report', 'action', 'from_status', 'to_status', 'from_level', 'to_level',
        'performed_by', 'performed_by_role', 'public_comment', 'internal_comment',
        'metadata', 'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

class ReportHistoryAdmin(admin.ModelAdmin):
    list_display = ('report_id','description', 'email', 'file', 'user', 'created_at')
    list_per_page = 10
    list_max_show_all = 10
admin.site.register(ReportHistory, ReportHistoryAdmin)


@admin.register(Ward)
class WardAdmin(admin.ModelAdmin):
    list_display = ['name']

@admin.register(Street)
class StreetAdmin(admin.ModelAdmin):
    list_display = ['name', 'ward']
    list_filter = ['ward']


class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'is_active', 'ward', 'street', 'registered_by' )  # Add 'is_active' to display
    search_fields = ('username', 'email')  # You can search by username or email
    list_filter = ('role', 'is_active')  # Add 'is_active' filter to the sidebar
    list_editable = ('is_active',)  # Allows admins to toggle 'is_active' from the list view
admin.site.register(CustomUser, CustomUserAdmin)


class OpenSpaceBookingAdmin(admin.ModelAdmin):
    list_display = ('username', 'contact', 'startdate', 'enddate', 'space', 'district', 'purpose', 'status', 'user')
admin.site.register(OpenSpaceBooking, OpenSpaceBookingAdmin)

class ForwardedBookingAdmin(admin.ModelAdmin):
    list_display = ('booking', 'ward_executive_description')
admin.site.register(ForwardedBooking, ForwardedBookingAdmin)

class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
admin.site.register(Notification, NotificationAdmin)

class UssdReportAdmin(admin.ModelAdmin):
    list_display = ('reference_number', 'open_space', 'description', 'status', 'phone_number')
admin.site.register(UssdReport, UssdReportAdmin)


class ReportForwardAdmin(admin.ModelAdmin):
    list_display = ('report','from_user', 'to_user')
admin.site.register(ReportForward, ReportForwardAdmin)

class ReportReplyVillageExecutiveAdmin(admin.ModelAdmin):
    list_display = ('report', 'from_user', 'message')
admin.site.register(ReportReplyVillageExecutive, ReportReplyVillageExecutiveAdmin)

class ReportForwardToadminAdmin(admin.ModelAdmin):
    list_display = ('report','from_user', 'to_user', 'message')
admin.site.register(ReportForwardToadmin, ReportForwardToadminAdmin)


class ReportReplyAdmin(admin.ModelAdmin):
    list_display = ('report', 'replied_by', 'message')
    list_per_page = 10
    list_max_show_all = 10
admin.site.register(ReportReply, ReportReplyAdmin)
