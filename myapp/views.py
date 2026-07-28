import uuid
from django.conf import settings
from .models import *
from django.forms import ValidationError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
import graphene
from graphene_django import DjangoObjectType
from graphql import GraphQLError # type: ignore
# from .tasks import send_verification_email # type: ignore
from .models import *
from openspaceBuilders.openspaceBuilders import UserBuilder, open_space, register_user, report_issue
from openspace_dto.openspace import *
from openspace_dto.Response import OpenspaceResponse, RegistrationResponse, ReportResponse
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from better_profanity import profanity # type: ignore
import os
from .utils import is_explicit_image, is_inappropriate_text
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework import permissions
from .serializers import *
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.decorators import parser_classes
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

class RegistrationMutation(graphene.Mutation):
    user = graphene.Field(RegistrationObject)
    output = graphene.Field(RegistrationResponse)

    class Arguments:
        input = RegistrationInputObject(required=True)

    def mutate(self, info, input):
        request = info.context
        auth = JWTAuthentication()
        registered_by = None
        try:
            user_auth_tuple = auth.authenticate(request)
            if user_auth_tuple is not None:
                registered_by, _ = user_auth_tuple
        except Exception as e:
            print("Token auth error:", str(e))
        response = register_user(input, registered_by=registered_by)
        return RegistrationMutation(user=response.user, output=response)

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

# @api_view(['GET'])
# def get_wards(request):
#     wards = Ward.objects.all().values_list('name', flat=True)
#     return Response(wards)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_wards(request):
    wards = Ward.objects.all().values('id', 'name')
    return Response(list(wards))



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_streets_for_loggedin_user_ward(request):
    user = request.user
    if user.ward:
        streets = Street.objects.filter(ward=user.ward)
        return Response(StreetSerializer(streets, many=True).data)
    return Response([])



class UserType(DjangoObjectType):
    class Meta:
        model = CustomUser
        fields = ("id", "username", "is_staff", "is_superuser", "role", "ward", "street")


class LoginUser(graphene.Mutation):
    class Arguments:
        username = graphene.String(required=True)
        password = graphene.String(required=True)

    user = graphene.Field(UserLoginObject)
    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, username, password):
        try:
            user = authenticate(username=username, password=password)

            if user is None:
                return LoginUser(success=False, message="Invalid credentials")
            
            if not isinstance(user, CustomUser):
                raise ValidationError("User is not a valid CustomUser instance.")

            # Create JWT token
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            user_data = UserLoginObject(
                id=user.id,
                username=user.username,
                token=access_token,
                isStaff=user.is_staff,
                isVillageChairman=(user.role == "village_chairman"),
                isWardExecutive=(user.role == "ward_executive")
            )

            return LoginUser(
                user=user_data,
                success=True,
                message=f"{user.role} login successful"
            )

        except Exception as e:
            return LoginUser(success=False, message=f"An error occurred: {str(e)}")



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_street_leaders_for_ward_executive(request):
    user = request.user

    street_leaders = CustomUser.objects.filter(
        role='village_chairman',
        registered_by=user
    )
    
    serializer = NewUserStreetSerializer(street_leaders, many=True)
    return Response(serializer.data)


class RegisterUserMutation(graphene.Mutation):
    class Arguments:
        input = UserRegistrationInput(required=True)

    Output = UserRegistrationObject

    def mutate(root, info, input):
        return UserBuilder.register_user(
            username=input.username,
            password=input.password,
            passwordConfirm=input.passwordConfirm
        )

class CreateOpenspaceMutation(graphene.Mutation):
    openspace = graphene.Field(OpenspaceObject)
    output = graphene.Field(OpenspaceResponse)
    
    class Arguments:
        input = OpenspaceInputObject(required=True)
        
    def mutate(self, info, input):
        response = open_space(input)
        
        return CreateOpenspaceMutation(openspace=response.openspace, output=response)
    

class DeleteOpenspace(graphene.Mutation):
    message = graphene.String()
    success = graphene.Boolean()
    
    class Arguments:
        id = graphene.ID(required=True)
        
    def mutate(self, info, id):
        try:
            open_space = OpenSpace.objects.get(pk=id)
            open_space.delete()
            return DeleteOpenspace(success=True, message="Openspace delete successfully")
        except OpenSpace.DoesNotExist:
            return DeleteOpenspace(success=False, message="Fail to delete openspace")
        

class ToggleOpenspaceMutation(graphene.Mutation):
    class Arguments:
        input = ToggleOpenspaceInput(required=True)

    openspace = graphene.Field(OpenspaceObject)

    def mutate(self, info, input):
        try:
            openspace = OpenSpace.objects.get(pk=input.id)
            openspace.is_active = input.is_active
            openspace.save()
            return ToggleOpenspaceMutation(openspace=openspace)
        except OpenSpace.DoesNotExist:
            raise Exception("OpenSpace not found")


class OpenspaceQuery(graphene.ObjectType):
    all_open_spaces_admin = graphene.List(OpenspaceObject)
    
    all_open_spaces_user = graphene.List(OpenspaceObject)
    
    def resolve_all_open_spaces_admin(self, info):
        return OpenSpace.objects.all()
    
    def resolve_all_open_spaces_user(self, info):
        return OpenSpace.objects.filter(is_active=True)

        
class TotalOpenSpaceQuery(graphene.ObjectType):
    total_openspaces = graphene.Int()
    
    def resolve_total_openspaces(self, info):
        return OpenSpace.objects.count()

class ReportMutation(graphene.Mutation):
    report = graphene.Field(ReportObject)
    output = graphene.Field(ReportResponse)
    
    class Arguments:
        input = ReportInputObject(required=True)
        
    def mutate(self, info, input):
        response = report_issue(input)
        return ReportMutation(report=response.report, output=response)
    
    
class ReportType(DjangoObjectType):
    class Meta:
        model = Report
        fields = "__all__"
        
    def resolve_file_url(self, info):
        if self.file:
            return f"{settings.MEDIA_URL}{self.file}"
        return None

profanity.load_censor_words()

ALLOWED_FILE_EXTENSIONS = ['.pdf', '.jpg', '.jpeg', '.png']
    
class CreateReport(graphene.Mutation):
    class Arguments:
        description = graphene.String(required=True)
        email = graphene.String(required=False)
        file_path = graphene.String(required=False)
        space_name = graphene.String(required=False)
        district = graphene.String(required=False)
        street = graphene.String(required=False)
        latitude = graphene.Float(required=False) 
        longitude = graphene.Float(required=False)
        user_id = graphene.ID(required=False)

    report = graphene.Field(ReportType)

    def mutate(self, info, description, email=None, file_path=None, space_name=None, district=None, street=None,
               latitude=None, longitude=None, user_id=None):


        if profanity.contains_profanity(description):
            raise GraphQLError("Description contains inappropriate language.")

        if file_path:
            ext = os.path.splitext(file_path)[1].lower()
            if ext not in ALLOWED_FILE_EXTENSIONS:
                raise GraphQLError("Invalid file type. Only PDF, JPG, and PNG are allowed.")

            if is_explicit_image(file_path):
                raise GraphQLError("Inappropriate image content detected.")

        user = None
        if user_id:
            try:
                user = CustomUser.objects.get(id=user_id)
            except CustomUser.DoesNotExist:
                raise GraphQLError("Invalid user ID.")

        report = Report(
            description=description,
            email=email,
            file=file_path,
            space_name=space_name,
            district=district,
            street=street,
            latitude=latitude,
            longitude=longitude,
            user=user,
        )
        report.save()

        return CreateReport(report=report)


class ReportQuery(graphene.ObjectType):
    all_reports = graphene.List(ReportType)
    
    def resolve_all_reports(self, info):
        return Report.objects.all()
    

class ConfirmReport(graphene.Mutation):
    message = graphene.String()
    success = graphene.Boolean()
    
    class Arguments:
        report_id = graphene.String(required=True)
        
    def mutate(self, info, report_id):
        try:
            report = Report.objects.get(report_id=report_id)
            
            ReportHistory.objects.create(
                report_id = report.report_id,
                description=report.description,
                email=report.email,
                file=report.file if report.file else None,
                user=report.user  # Link the report to the original user
            )
            
            # Delete the original report
            report.delete()
            
            # Send email if user provided one
            if report.email:
                send_mail(
                    subject="Report Confirmation",
                    message="Your report has been reviewed and confirmed.",
                    from_email="limbureubenn@gmail.com",
                    recipient_list=[report.email],
                    fail_silently=True
                )
                
            return ConfirmReport(success=True, message="Report confirmed and moved to history.")
        except Report.DoesNotExist:
            return ConfirmReport(success=False, message="Report not found.")

        
class DeleteReport(graphene.Mutation):
    message = graphene.String()
    success = graphene.String()
    
    class Arguments:
        report_id = graphene.ID(required=True)
    def mutate(self, info, report_id):
        try:
            report = Report.objects.get(pk=report_id)
            report.delete()
            return DeleteReport(success=True, message="Report deleted successfully")
        except report.DoesNotExist:
            return DeleteReport(success=False, message="Report not found")
        
class HistoryReportQuery(graphene.ObjectType):
    all_historys = graphene.List(HistoryObject)
    
    def resolve_all_historys(self, info):
        return ReportHistory.objects.all()
    
class HistoryCountQuery(graphene.ObjectType):
    total_historys = graphene.Int()
    
    def resolve_total_historys(self, info):
        return ReportHistory.objects.count()
    
class ReportCountQuery(graphene.ObjectType):
    total_report = graphene.Int()
    
    def resolve_total_report(self, info):
        return Report.objects.count()
    
class ReportAnonymousQuery(graphene.ObjectType):
    anonymous = graphene.List(HistoryObject, session_id=graphene.String(required=True))
    
    def resolve_anonymous(self, info, session_id):
        return ReportHistory.objects.filter(session_id=session_id)
    


class AuthenticatedUserReport(graphene.ObjectType):
    my_reports = graphene.List(HistoryObject)
    
    def resolve_my_reports(self, info, **kwargs):
        user = info.context.user
        print("Authenticated user:", user)  # Debugging

        if user.is_authenticated:
            reports = UserBuilder.get_report_history(user=user)
            print(reports)  # Debugging
            return reports

        print("User is anonymous or not authenticated.")
        return ReportHistory.objects.none()


from graphql_jwt.decorators import login_required # type: ignore

User = get_user_model()

from rest_framework_simplejwt.tokens import AccessToken


class UserProfileQuery(graphene.ObjectType):
    profile=graphene.Field(ProfileObject)
    
    def resolve_profile(self,info):
        user=info.context.user
        if user.is_authenticated:
            return UserBuilder.get_user_profile_data(user=user)
            

class QueryUsers(graphene.ObjectType):
    ward_exectives = graphene.List(UserAllObject)

    def resolve_ward_exectives(root, info):
        users = CustomUser.objects.filter(role='ward_executive')
        return [
            UserAllObject(
                pk=user.pk,
                username=user.username,
                email=user.email,
                ward = user.ward,
                is_staff = user.is_staff,
                role = user.role,
            )
        for user in users
        ]
    


class BookedOpenSpaceQuery(graphene.ObjectType):
    booked_openspace = graphene.List(BookedOpenspaceObject)
    def resolve_booked_openspace(self, info):
        return OpenSpaceBooking.objects.all()



# CustomerUser = get_user_model()
# class ReplyToReportAPIView(APIView):
#     permission_classes = [permissions.IsAdminUser]

#     def post(self, request):
#         report_id = request.data.get('report_id')
#         message = request.data.get('message')

#         if not report_id or not message:
#             return Response({'error': 'Missing report_id or message'}, status=400)

#         try:
#             report = Report.objects.get(report_id=report_id)
#         except Report.DoesNotExist:
#             return Response({'error': 'Report not found'}, status=404)

#         try:
#             reply = ReportReply.objects.create(
#                 report=report,
#                 sender=request.user if request.user.is_authenticated else None,
#                 message=message
#             )
#             reply.save()

#             # Send email if email exists
#             if report.email:
#                 send_mail(
#                     subject="Reply to Your Report",
#                     message=message,
#                     from_email=settings.DEFAULT_FROM_EMAIL,
#                     recipient_list=[report.email],
#                     fail_silently=False,
#                 )
#             return Response({'success': 'Reply sent successfully'}, status=200)
#         except Exception as e:
#             return Response({'error': str(e)}, status=400)






import os
from django.shortcuts import render
import graphene
from graphene_django import DjangoObjectType

from .tasks import send_reset_email_task
from rest_framework.views import APIView # type: ignore
from rest_framework.response import Response # type: ignore
from rest_framework import status # type: ignore
from rest_framework.permissions import IsAuthenticated
from .serializers import *
from django.contrib.auth.tokens import default_token_generator

from rest_framework.decorators import api_view # type: ignore
from rest_framework.response import Response # type: ignore
from rest_framework import status # type: ignore
from .models import *
# from myapp.models import *
from .serializers import ProblemReportSerializer
from cryptography.fernet import Fernet # type: ignore

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.auth import get_user_model
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.conf import settings
from django.utils.http import urlsafe_base64_decode
from rest_framework.decorators import api_view, permission_classes
from .booking_sms import send_sms


# views.py
from rest_framework.parsers import MultiPartParser, FormParser # type: ignore
from rest_framework.response import Response # type: ignore
from rest_framework.views import APIView # type: ignore
from rest_framework import status # type: ignore
from django.core.files.storage import default_storage




















class FileUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        file_obj = request.FILES.get('file')
        if not file_obj:
            # No file provided, which is okay
            return Response({'file_path': None}, status=status.HTTP_200_OK)
        
        file_path = default_storage.save(f'reports/{file_obj.name}', file_obj)
        return Response({'file_path': file_path}, status=status.HTTP_201_CREATED)
    
    
fernet = Fernet(settings.FERNET_KEY)

@api_view(['POST'])
def submit_problem_report(request):
    try:
        # Get data from the incoming request
        phone_number = request.data['phone_number']
        open_space = request.data['open_space']
        description = request.data['description']
        reference_number = request.data['reference_number']

        # Encrypt the phone number before saving
        encrypted_phone = fernet.encrypt(phone_number.encode()).decode()

        report = UssdReport.objects.create(
            phone_number=encrypted_phone,
            open_space=open_space,
            description=description,
            reference_number=reference_number,
            status="Pending"
        )

        serializer = ProblemReportSerializer(report)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    except KeyError as e:
        return Response({'error': f'Missing key: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({'error': f'An error occurred: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConfirmReportAPIView(APIView):
    def post(self, request, pk):
        try:
            report = UssdReport.objects.get(pk=pk)
            if report.status != 'processed':
                report.status = 'processed'
                report.save()

                # Send SMS to user
                message = f"Hello {report.username}, your report #{report.reference} has been confirmed."
                send_sms(report.phone_number, message)

                return Response({'message': 'Report confirmed and SMS sent.'}, status=status.HTTP_200_OK)
            return Response({'message': 'Report already processed.'}, status=status.HTTP_200_OK)
        except UssdReport.DoesNotExist:
            return Response({'error': 'Report not found'}, status=status.HTTP_404_NOT_FOUND)



@api_view(['GET'])
def get_report_status(request, reference_number):
    try:
        # Find the report by reference number
        report = UssdReport.objects.get(reference_number=reference_number)
        serializer = ProblemReportSerializer(report)
        return Response({
            "reference_number": report.reference_number,
            "status": report.status
        }, status=status.HTTP_200_OK)
    except UssdReport.DoesNotExist:
        return Response({"error": "Report not found"}, status=status.HTTP_404_NOT_FOUND)


class UssdReportType(DjangoObjectType):
    class Meta:
        model = UssdReport

class ReportUssdQuery(graphene.ObjectType):
    all_reports_ussds = graphene.List(UssdReportType)
    def resolve_all_reports_ussds(self, info):
        # Fetch all reports
        return UssdReport.objects.all()
    


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class ProfileImageUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ProfileImageUploadSerializer(instance=request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            image_url = request.build_absolute_uri(serializer.data['profile_image'])
            return Response({'imageUrl': image_url}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user, context={'request': request})
        return Response(serializer.data)



CustomUser = get_user_model()

class SendResetPasswordEmailView(APIView):
    def post(self, request):
        print("PasswordResetRequestView POST called")

        email = request.data.get('email')
        if not email:
            return Response({'error': 'Email is required'}, status=400)

        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_link = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"

        # Use Celery to send the email asynchronously
        send_reset_email_task.delay(email, reset_link)

        return Response({'message': 'Password reset link sent to email.'}, status=200)


class PasswordResetConfirmView(APIView):
    def post(self, request):
        uidb64 = request.data.get("uid")
        token = request.data.get("token")
        new_password = request.data.get("password")

        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = CustomUser.objects.get(pk=uid)

            if PasswordResetTokenGenerator().check_token(user, token):
                user.set_password(new_password)
                user.save()
                return Response({"message": "Password reset successful"})
            else:
                return Response({"error": "Invalid token"}, status=400)
        except Exception as e:
            return Response({"error": str(e)}, status=400)




class OpenSpaceBookingView(APIView):
    def post(self, request):
        serializer = OpenSpaceBookingSerializer(
            data=request.data,
            context={'request': request}  # Pass the request to the serializer context
        )

        if serializer.is_valid():
            # Save booking and associate with the logged-in user
            booking = serializer.save(user=request.user)

            # Mark the space as unavailable
            booking.space.status = 'unavailable'
            booking.space.save()

            return Response(OpenSpaceBookingSerializer(booking).data, status=status.HTTP_201_CREATED)

        print("Booking validation errors:", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



from django.db.models import Q

class DistrictBookingsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role != "ward_executive":
            return Response({"error": "Unauthorized"}, status=403)

        forwarded_booking_ids = ForwardedBooking.objects.values_list('booking_id', flat=True)
        bookings = OpenSpaceBooking.objects.filter(
            district=user.ward
        ).exclude(id__in=forwarded_booking_ids)

        serializer = OpenSpaceBookingSerializer(bookings, many=True)
        return Response(serializer.data)

    

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_and_forward_booking(request, booking_id):
    user = request.user
    if user.role != "ward_executive":
        return Response({"error": "Unauthorized"}, status=403)

    try:
        booking = OpenSpaceBooking.objects.get(id=booking_id, district=user.ward)
    except OpenSpaceBooking.DoesNotExist:
        return Response({"error": "Booking not found or unauthorized"}, status=404)

    ward_executive_description = request.data.get('description', '').strip()
    if not ward_executive_description:
        return Response({"error": "Description is required"}, status=400)

    forwarded_booking = ForwardedBooking.objects.create(
        booking=booking,
        ward_executive_description=ward_executive_description,
        forwarded_by=user
    )
    return Response({"message": "Booking accepted and forwarded to admin"}, status=200)


class ForwadedBookingAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        forwarded_bookings = ForwardedBooking.objects.filter(forwarded_by=user)
        serializer = ForwardedBookingSerializer(forwarded_bookings, many=True)
        return Response(serializer.data)


class AllBookingsAdminAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        user = request.user

        if user.role != "staff":
            return Response({"error": "Unauthorized"}, status=403)
        bookings = OpenSpaceBooking.objects.all().order_by('-created_at')
        serializer = OpenSpaceBookingSerializer(bookings, many=True)
        return Response(serializer.data)
    


@api_view(['POST'])
def reject_booking(request, booking_id):
    try:
        booking = OpenSpaceBooking.objects.get(id=booking_id)

        # Update booking status
        booking.status = 'rejected'
        booking.save()

        # Update OpenSpace status to available
        booking.space.status = 'available'
        booking.space.save()

        # Send rejection email if email exists
        user_email = None
        if booking.user and booking.user.email:
            user_email = booking.user.email
        elif hasattr(booking, 'email') and booking.email:
            user_email = booking.email

        if user_email:
            subject = 'Your Booking Has Been Rejected'
            message = f"""
Hello {booking.username},

Your booking for {booking.space.name} from {booking.startdate} to {booking.enddate} has been rejected.
The space is now available for others.

Thank you for understanding.
"""
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user_email],
                fail_silently=True
            )

        # Send SMS notification if contact exists
        if booking.contact:
            sms_message = f"Hello {booking.username}, your booking for {booking.space.name} from {booking.startdate} to {booking.enddate} has been Rejected please Visit your ward office for more information."
            try:
                send_sms(phone=booking.contact, message=sms_message)
            except Exception as e:
                print("Failed to send rejection SMS:", e)

        return Response({'message': 'Booking rejected successfully.'}, status=status.HTTP_200_OK)

    except OpenSpaceBooking.DoesNotExist:
        return Response({'error': 'Booking not found.'}, status=status.HTTP_404_NOT_FOUND)






@api_view(['POST'])
def accept_booking(request, booking_id):
    try:
        booking = OpenSpaceBooking.objects.get(id=booking_id)

        # 1. Update booking status to 'accepted'
        booking.status = 'accepted'
        booking.save()

        # 2. Mark open space as 'unavailable'
        booking.space.status = 'unavailable'
        booking.space.save()

        # 3. Send SMS notification to user
        if booking.contact:
            sms_message = (
                f"Hello {booking.username}, your booking for {booking.space.name} "
                f"from {booking.startdate} to {booking.enddate} has been ACCEPTED. "
                f"Please prepare accordingly."
            )
            try:
                send_sms(phone=booking.contact, message=sms_message)
            except Exception as e:
                print("Failed to send acceptance SMS:", e)

        return Response({'message': 'Booking accepted and user notified.'}, status=status.HTTP_200_OK)

    except OpenSpaceBooking.DoesNotExist:
        return Response({'error': 'Booking not found.'}, status=status.HTTP_404_NOT_FOUND)




class UserBooking(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        bookings = OpenSpaceBooking.objects.filter(user=user).order_by('-created_at')
        serializer = OpenSpaceBookingSerializer(bookings, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

from rest_framework import generics, permissions

class MyBookingsView(generics.ListAPIView):
    serializer_class = OpenSpaceBookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Get bookings for the logged-in user
        return OpenSpaceBooking.objects.filter(user=self.request.user).order_by('-created_at')



from rest_framework.decorators import api_view # type: ignore
from rest_framework.response import Response # type: ignore
from .sms import send_sms
from .utils import decrypt_phone_number

@api_view(['POST'])
def confirm_report(request, report_id):
    try:
        report = UssdReport.objects.get(id=report_id)
        decrypted_phone = decrypt_phone_number(report.phone_number)

        message = (
            f"Hello! Your report with reference number {report.reference_number} "
            f"regarding '{report.open_space}' has been successfully confirmed. "
            f"Thank you for helping us improve our community."
        )

        response = send_sms(decrypted_phone, message)
        report.status = 'processed'
        report.save()

        return Response({"status": "success", "data": response})

    except UssdReport.DoesNotExist:
        return Response({"status": "error", "message": "Report not found"}, status=404)

    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=500)



@api_view(['POST'])
def reply_to_report(request, report_id):
    try:
        report = UssdReport.objects.get(id=report_id)
        decrypted_phone = decrypt_phone_number(report.phone_number)

        custom_message = request.data.get("message", "")
        if not custom_message:
            return Response({"status": "error", "message": "Message content is required"}, status=400)

        response = send_sms(decrypted_phone, custom_message)

        return Response({"status": "success", "message": "Reply sent successfully", "data": response})

    except UssdReport.DoesNotExist:
        return Response({"status": "error", "message": "Report not found"}, status=404)


@api_view(['DELETE'])
def delete_report(request, report_id):
    try:
        report = UssdReport.objects.get(id=report_id)
        report.delete()
        return Response({"status": "success", "message": "Report deleted successfully"})
    
    except UssdReport.DoesNotExist:
        return Response({"status": "error", "message": "Report not found"}, status=404)
    
    except Exception as e:
        return Response({"status": "error", "message": str(e)}, status=500)



class DeleteBookingAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, booking_id):
        try:
            booking = OpenSpaceBooking.objects.get(id=booking_id)

            # Optional: only allow deletion by staff or the booking owner
            if request.user != booking.user and not request.user.is_staff:
                return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

            booking.delete()
            return Response({'message': 'Booking deleted successfully'}, status=status.HTTP_204_NO_CONTENT)

        except OpenSpaceBooking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_booking_stats(request):
    user = request.user
    bookings = OpenSpaceBooking.objects.filter(user=user)

    total = bookings.count()
    accepted = bookings.filter(status='accepted').count()
    pending = bookings.filter(status='pending').count()

    return Response({
        'total': total,
        'accepted': accepted,
        'pending': pending
    })


class NotifyAllWardExecutivesView(APIView):
    def post(self, request):
        message = request.data.get('message')
        if not message:
            return Response({'error': 'Message is required'}, status=status.HTTP_400_BAD_REQUEST)

        ward_executives = CustomUser.objects.filter(role='ward_executive').exclude(email='')

        for executive in ward_executives:
            send_mail(
                subject='Notification from Kinondoni Municipal',
                message=message,
                from_email='limbureubenn@gmail.com',
                recipient_list=[executive.email],
                fail_silently=True
            )

        return Response({'success': 'Notifications sent to all ward executives.'}, status=status.HTTP_200_OK)


class NotifySingleWardExecutiveView(APIView):
    def post(self, request):
        email = request.data.get('email')
        message = request.data.get('message')

        if not email or not message:
            return Response({'error': 'Email and message are required'}, status=status.HTTP_400_BAD_REQUEST)

        send_mail(
            subject='Notification from Kinondoni Municipal',
            message=message,
            from_email='admin@example.com',  # Replace with your configured email
            recipient_list=[email],
            fail_silently=True
        )

        return Response({'success': f'Notification sent to {email}'}, status=status.HTTP_200_OK)



class UserReportHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reports = Report.objects.filter(user=request.user).order_by('-created_at')
        serializer = ReportSerializer(reports, many=True)
        return Response(serializer.data)



class DeleteBookingView(generics.DestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = OpenSpaceBooking.objects.all()

    def delete(self, request, *args, **kwargs):
        try:
            booking = self.get_queryset().get(pk=kwargs['pk'], user=request.user)
        except OpenSpaceBooking.DoesNotExist:
            return Response({'error': 'Booking not found'}, status=status.HTTP_404_NOT_FOUND)

        if booking.status == 'pending':
            return Response(
                {'error': 'Cannot delete a booking that is still pending.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        booking.delete()
        return Response({'message': 'Booking deleted successfully.'}, status=status.HTTP_204_NO_CONTENT)



class SendNotificationView(APIView):
    def post(self, request):
        user_id = request.data.get('user_id')
        message = request.data.get('message')
        print("DEBUG Request Data:", request.data)

        if not user_id or not message:
            return Response({'error': 'User ID and message are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        notification = Notification.objects.create(user=user, message=message)
        serializer = NotificationSerializer(notification)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class UnreadNotificationCountAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        count = Notification.objects.filter(user=user, is_read=False).count()
        return Response({'unread_count': count})


class VillageChairmenByWardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role != 'ward_executive':
            return Response(
                {'detail': 'Only ward executives can access this resource.'},
                status=status.HTTP_403_FORBIDDEN
            )

        chairmen = CustomUser.objects.filter(
            role='village_chairman',
            registered_by=user
        )

        serializer = UserStreetSerializer(chairmen, many=True)
        return Response(serializer.data)



@api_view(['GET'])
@permission_classes([AllowAny])
def get_wards(request):
    wards = Ward.objects.all().values('id', 'name')
    return Response(wards)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_streets_by_ward(request):
    ward_name = request.GET.get('ward')
    if not ward_name:
        return Response({"error": "Ward name is required"}, status=400)

    try:
        ward = Ward.objects.get(name=ward_name)
    except Ward.DoesNotExist:
        return Response({"error": "Ward not found"}, status=404)

    streets = Street.objects.filter(ward=ward)
    serializer = SimpleStreetSerializer(streets, many=True)
    return Response(serializer.data)



@api_view(['POST'])
@permission_classes([AllowAny])
@parser_classes([MultiPartParser, FormParser])
def create_report(request):
    user = request.user if request.user.is_authenticated else None

    serializer = ReportSerializer(data=request.data)
    if serializer.is_valid():
        report = serializer.save(user=user)
        return Response({
            'message': 'Report submitted successfully',
            'reportId': report.report_id
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



from django.db.models.functions import Lower

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def reports_by_street_name_match(request):
    user = request.user

    if not user.street:
        return Response({'error': 'User is not assigned to any street'}, status=status.HTTP_400_BAD_REQUEST)

    # Normalize user street name
    user_street_name = user.street.name.strip().lower()

    # Match using __icontains for more flexible match
    reports = Report.objects.annotate(
        street_lower=Lower('street')
    ).filter(street_lower__icontains=user_street_name).order_by('-created_at')

    serializer = ReportSerializer(reports, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)




import re
def normalize_street(name):
    """Normalize street name: lowercase, remove parentheses content, trim spaces"""
    if not name:
        return ""
    name = re.sub(r'\(.*?\)', '', name)  # remove text inside parentheses
    return name.strip().lower()

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def forward_report_to_ward_exec(request, report_id):
    user = request.user

    if user.role != 'village_chairman':
        return Response({'error': 'Only village chairmen can forward reports'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        report = Report.objects.get(pk=report_id)
    except Report.DoesNotExist:
        return Response({'error': 'Report not found'}, status=status.HTTP_404_NOT_FOUND)

    # Normalize street names
    report_street = normalize_street(report.street or report.street_name_backup)
    user_street = normalize_street(user.street.name if user.street else "")

    # Ensure report belongs to chairman's street
    if user_street not in report_street:
        print(f"Street mismatch: report='{report_street}' vs user='{user_street}'")
        return Response({'error': 'This report does not belong to your street'}, status=status.HTTP_403_FORBIDDEN)

    # Check if already forwarded
    if ReportForward.objects.filter(report=report, from_user=user).exists():
        return Response({'error': 'You have already forwarded this report'}, status=status.HTTP_400_BAD_REQUEST)

    # Get ward executive who registered this chairman
    ward_exec = user.registered_by
    if not ward_exec or ward_exec.role != 'ward_executive':
        return Response({'error': 'No ward executive assigned'}, status=status.HTTP_400_BAD_REQUEST)

    # Create forwarding record
    message = request.data.get('message', '')
    forward_record = ReportForward.objects.create(
        report=report,
        from_user=user,
        to_user=ward_exec
    )

    # Log forwarding for debugging
    print(f"Report '{report.report_id}' forwarded from '{user.username}' to '{ward_exec.username}'")

    return Response({'success': f"Report forwarded to {ward_exec.username}"}, status=status.HTTP_200_OK)




@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reply_to_report(request, report_id):
    user = request.user

    # Only village chairmen can reply
    if user.role != 'village_chairman':
        return Response({'error': 'Only village chairmen can reply'}, status=status.HTTP_403_FORBIDDEN)

    try:
        report = Report.objects.get(pk=report_id)
    except Report.DoesNotExist:
        return Response({'error': 'Report not found'}, status=status.HTTP_404_NOT_FOUND)

    message = request.data.get('message', '').strip()
    if not message:
        return Response({'error': 'Message cannot be empty'}, status=status.HTTP_400_BAD_REQUEST)

    # Create reply
    reply = ReportReplyVillageExecutive.objects.create(
        report=report,
        from_user=user,
        message=message
    )

    serializer = ReportReplySerializer(reply)
    return Response(serializer.data, status=status.HTTP_201_CREATED)



# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def forwarded_reports_for_ward(request):
#     """
#     Fetch all reports forwarded to the logged-in ward executive.
#     """
#     user = request.user

#     if user.role != 'ward_executive':
#         return Response({'error': 'Only ward executives can access this'}, status=403)

#     # Fetch all ReportForward entries where the logged-in user is the recipient
#     forwarded = ReportForward.objects.filter(to_user=user).order_by('-forwarded_at')

#     reports_data = [
#         {
#             'report_id': f.report.report_id,
#             'space_name': f.report.space_name,  # <-- include the open space
#             'district': f.report.district,
#             'street': f.report.street,
#             'description': f.report.description,
#             'from_user': f.from_user.username if f.from_user else None,
#             'message': f.message,
#             'forwarded_at': f.forwarded_at,
#         }
#         for f in forwarded
#     ]

#     return Response(reports_data, status=200)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def forwarded_reports_for_ward(request):
    """
    Fetch all reports forwarded to the logged-in ward executive.
    """
    user = request.user

    if user.role != 'ward_executive':
        return Response({'error': 'Only ward executives can access this'}, status=403)

    # Fetch all ReportForward entries where the logged-in user is the recipient
    forwarded = (
        ReportForward.objects
        .filter(to_user=user)
        .select_related('report', 'from_user')
        .order_by('-forwarded_at')
    )

    reports_data = []
    for f in forwarded:
        reports_data.append({
            'id': f.id,  # <-- Forward record ID (needed for forwarding to admin)
            'report_id': f.report.report_id,
            'space_name': f.report.space_name,
            'district': f.report.district,
            'street': f.report.street,
            'description': f.report.description,
            'from_user': f.from_user.username if f.from_user else None,
            'forwarded_at': f.forwarded_at,
            # Check if already forwarded to admin by this ward executive
            'forwarded_to_admin': ReportForwardToadmin.objects.filter(
                report=f.report,
                from_user=user
            ).exists()
        })

    return Response(reports_data, status=200)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def forward_report_to_admin_from_village(request, forward_id):
    """
    Ward executive forwards a report they received from a village chairman
    to the admin who registered them.
    """
    user = request.user

    if user.role != 'ward_executive':
        return Response({'error': 'Only ward executives can forward reports'}, status=403)

    try:
        # Ensure the ward executive is the recipient of this forward
        forwarded_report = ReportForward.objects.get(pk=forward_id, to_user=user)
    except ReportForward.DoesNotExist:
        return Response({'error': 'Forwarded report not found or not assigned to you'}, status=404)

    # Get the admin who registered this ward executive
    admin_user = getattr(user, 'registered_by', None)
    if not admin_user or getattr(admin_user, 'role', '') != 'staff':
        return Response({'error': 'No valid admin registered this ward executive'}, status=400)

    # Prevent duplicate forwarding to admin
    if ReportForwardToadmin.objects.filter(report=forwarded_report.report, from_user=user, to_user=admin_user).exists():
        return Response({'error': 'This report has already been forwarded to admin'}, status=400)

    # Create forward entry
    ReportForwardToadmin.objects.create(
        report=forwarded_report.report,
        from_user=user,
        to_user=admin_user,
    )

    return Response({'success': f"Report forwarded to admin {admin_user.username}"}, status=200)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def forwarded_reports_to_admin(request):
    """
    Fetch all reports forwarded to the logged-in admin.
    """
    user = request.user

    if user.role != 'staff':  # only admins
        return Response({'error': 'Only admin users can access this'}, status=403)

    # Fetch all ReportForwardToadmin entries for this admin
    forwarded = (
        ReportForwardToadmin.objects
        .filter(to_user=user)
        .select_related('report', 'from_user')
        .order_by('-forwarded_at')
    )

    reports_data = []
    for f in forwarded:
        reports_data.append({
            'id': f.report.id,  # Forward record ID
            'report_id': f.report.report_id,
            'space_name': f.report.space_name,
            'latitude': f.report.latitude,
            'longitude': f.report.longitude,
            'district': f.report.district,
            'street': f.report.street,
            'description': getattr(f.report, 'description', ''),
            'from_user': f.from_user.username if f.from_user else None,
            'message': getattr(f, 'message', ''),  # include if you added message field
            'forwarded_at': f.forwarded_at,
            'file': f.report.file.url if hasattr(f.report, 'file') and f.report.file else None
        })

    return Response(reports_data, status=200)



class WardRegisterAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def post(self, request):
        """
        Register a new ward.
        Example payload:
        {
            "name": "Ilala"
        }
        """
        ward_name = request.data.get("name", "").strip()

        if not ward_name:
            return Response({"error": "Ward name is required"}, status=status.HTTP_400_BAD_REQUEST)

        if Ward.objects.filter(name__iexact=ward_name).exists():
            return Response({"error": "Ward already exists"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = WardSerializer(data={"name": ward_name})
        if serializer.is_valid():
            serializer.save()
            return Response({"ward": serializer.data}, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        """
        List all wards for dropdowns.
        """
        wards = Ward.objects.all()
        serializer = WardSerializer(wards, many=True)
        return Response({"wards": serializer.data})

class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_staff


class StreetRegisterAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminUser]

    def get(self, request):
        """
        Return all wards for dropdown + optional list of streets
        """
        wards = Ward.objects.all()
        streets = Street.objects.select_related('ward').all()

        return Response({
            "wards": WardSerializer(wards, many=True).data,
            "streets": StreetSerializer(streets, many=True).data
        })

    def post(self, request):
        """
        Accept multiple streets for a ward.
        Example payload:
        {
            "wardName": "Kinondoni",
            "streets": ["Uhuru Street", "Mtaa wa Juu", "Kigogo"]
        }
        """
        ward_name = request.data.get("wardName")
        street_names = request.data.get("streets", [])

        if not ward_name or not street_names:
            return Response({"error": "Ward name and streets are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ward = Ward.objects.get(name=ward_name)
        except Ward.DoesNotExist:
            return Response({"error": "Ward not found"}, status=status.HTTP_404_NOT_FOUND)

        created_streets = []
        for name in street_names:
            name = name.strip()
            if name:  # avoid empty names
                serializer = StreetSerializer(data={"name": name, "ward": ward.id})
                if serializer.is_valid():
                    serializer.save()
                    created_streets.append(serializer.data)

        return Response({"created": created_streets}, status=status.HTTP_201_CREATED)


from django.shortcuts import get_object_or_404
class ForwardReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):  
        """
        Forward a report (pk) from the logged-in village executive 
        to the ward executive who registered that village executive.
        """
        # 1. Get the report
        report = get_object_or_404(Report, pk=pk)

        if request.user.role != "village_chairman":
            return Response(
                {"error": "Only village executives can forward reports"},
                status=status.HTTP_403_FORBIDDEN
            )

        # 3. Find the ward executive who registered this village executive
        ward_exec = request.user.registered_by

        if not ward_exec or ward_exec.role != "ward_executive":
            return Response(
                {"error": "No ward executive linked to this village executive"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 4. Create a forward entry
        ReportForward.objects.create(
            report=report,
            forwarded_by=request.user,
            forwarded_to=ward_exec
        )

        return Response(
            {"message": f"Report forwarded to {ward_exec.username}"},
            status=status.HTTP_201_CREATED
        )
        
        
        
        
class ReportReplyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        """
        Admin replies to a report. In-app notification stored in ReportReply
        and optional email sent to reporter if email exists.
        """
        user = request.user  # Admin
        try:
            report = Report.objects.get(id=id)
        except Report.DoesNotExist:
            return Response({'error': 'Report not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ReportReplySerializer(data=request.data)
        if serializer.is_valid():
            reply = serializer.save(report=report, replied_by=user)
            message = serializer.validated_data['message']

            # Optional: Send email to reporter
            recipient_email = report.user.email if report.user and report.user.email else report.email
            if recipient_email:
                try:
                    send_mail(
                        subject=f"Response to your report {report.report_id}",
                        message=message,
                        from_email='limbureubenn@gmail.com',
                        recipient_list=[recipient_email],
                        fail_silently=True
                    )
                except Exception as e:
                    print(f"Failed to send reply email: {e}")

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# views.py
class UserNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Fetch all replies as notifications for the logged-in user.
        """
        reports = Report.objects.filter(user=request.user)
        replies = ReportReply.objects.filter(report__in=reports).order_by('-created_at')
        serializer = ReportNotificationSerializer(replies, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)



# @api_view(['GET'])
# @permission_classes([IsAuthenticated])
# def my_report_replies(request):
#     replies = ReportReply.objects.filter(report__user=request.user).order_by('-created_at')
#     serializer = ReportReplySerializer(replies, many=True)
#     return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_report_replies(request):
    user = request.user
    reports = Report.objects.filter(user=user)  # only the user's reports
    replies = ReportReply.objects.filter(report__in=reports).select_related('replied_by', 'report').order_by('-created_at')

    data = [
        {
            'id': r.id,
            'report_id': r.report.report_id,
            'message': r.message,
            'replied_by': r.replied_by.username if r.replied_by else None,
            'created_at': r.created_at
        }
        for r in replies
    ]
    return Response(data)


class WardDashboardCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role != 'ward_executive' or not user.ward:
            return Response({"error": "Only ward executives can access this"}, status=403)

        # --- OpenSpaces counts ---
        total_openspaces = OpenSpace.objects.filter(district=user.ward).count()
        available_openspaces = OpenSpace.objects.filter(district=user.ward, status="available").count()
        unavailable_openspaces = OpenSpace.objects.filter(district=user.ward, status="unavailable").count()

        # --- Reports counts ---
        total_reports = ReportForward.objects.filter(to_user=user).count()
        forwarded_to_admin = ReportForwardToadmin.objects.filter(from_user=user).count()
        pending_reports = total_reports - forwarded_to_admin

        return Response({
            "ward": user.ward.name,
            "openspaces": {
                "total": total_openspaces,
                "available": available_openspaces,
                "unavailable": unavailable_openspaces,
            },
            "reports": {
                "total": total_reports,
                "forwarded_to_admin": forwarded_to_admin,
                "pending": pending_reports,
            }
        })
