from collections import defaultdict
from datetime import date, timedelta, datetime
from email.mime.text import MIMEText
import smtplib
from django.db.models import Sum
import pandas as pd
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import AllowAny
from core_app.auth import EmailAuthBackend
from .jwt_utils import get_user_from_token, verify_token, generate_token
from .models import TimesheetEmailLog, User, Timesheet, Project, UserProject
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import get_user_model, authenticate
from django.db.models import Case, When, Value, FloatField, Sum
from datetime import date, timedelta
import calendar
from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from .models import AutomationTimesheet, TimesheetType
from .utils.json_utils import convert_decimals,normalize_dict
from django.db.models import Max
from django.utils.dateparse import parse_date
from django.utils.timezone import is_naive, make_aware, get_current_timezone
from .serializers import (
    UserSerializer, 
    RegisterSerializer,
    LoginSerializer, 
    TimesheetSerializer,
    ProjectSerializer,
    UserProjectSerializer,
    MyTokenObtainPairSerializer,
    UploadExcelSerializer, 
    UploadTimesheetSerializer,
    GenerateTemplateSerializer,
    EmailSerializer
)
import jwt
import base64
import json
import logging
import os
from django.conf import settings
from core_app.utils.email_utils import EmailSender
from scripts.ppt_generator import generate_presentation
from scripts.timesheet_validation import TimeValidator, OutputManager
from django.http import FileResponse
from django.db.models import Q, Sum, Case, When, Value, FloatField
from django.utils.timezone import now

logger = logging.getLogger(__name__)

def debug_token(token_str):
    """Inspect and debug a JWT token without validation"""
    try:
        parts = token_str.split('.')
        if len(parts) != 3:
            return {"error": "Not a valid JWT format (should have 3 parts)"}
        def decode_part(part):
            padding = '=' * (4 - len(part) % 4)
            return json.loads(base64.b64decode(part + padding).decode('utf-8'))
            
        header = decode_part(parts[0])
        payload = decode_part(parts[1])
        
        return {
            "header": header,
            "payload": payload,
            "is_valid_format": True
        }
    except Exception as e:
        logger.error(f"Token debug failed: {str(e)}")
        return {"error": f"Failed to decode token: {str(e)}"}

def get_user_from_request(request):
    """Extract and return the user from the Authorization token"""
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return None

    token = auth_header.split(' ')[1]

    try:
        try:
            payload = jwt.decode(
                token,
                settings.SIMPLE_JWT['SIGNING_KEY'],
                algorithms=['HS256'],
                options={'verify_exp': True}
            )
            user_id = payload.get('sub') or payload.get('user_id')
            if not user_id:
                return None
            User = get_user_model()
            return User.objects.get(id=user_id)
            
        except Exception:
            user = get_user_from_token(token)
            return user
            
    except Exception:
        try:
            User = get_user_model()
            token_obj = AccessToken(token)
            user_id = token_obj.payload.get('user_id')
            if user_id:
                return User.objects.get(id=user_id)
        except Exception:
            return None
def generate_password_reset_token(user_id):
    payload = {
        "user_id": user_id,
        "type": "password_reset",
        "exp": datetime.utcnow() + timedelta(hours=1),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, settings.SIMPLE_JWT['SIGNING_KEY'], algorithm='HS256')

def verify_password_reset_token(token):
    try:
        payload = jwt.decode(token, settings.SIMPLE_JWT['SIGNING_KEY'], algorithms=['HS256'])
        if payload.get("type") != "password_reset":
            raise jwt.InvalidTokenError("Incorrect token type")
        return payload["user_id"]
    except (jwt.ExpiredSignatureError, jwt.DecodeError, jwt.InvalidTokenError) as e:
        logger.error(f"Invalid password reset token: {str(e)}")
        raise ValueError("Invalid or expired token")


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

#Users Api
class UserListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        User = get_user_model()
        users = User.objects.all().values('id', 'name', 'email')
        return Response(users)

#Register API
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                "status": "error",
                "code": "invalid_input",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = serializer.save()

            return Response({
                "status": "success",
                "message": "User registered successfully. Please log in to continue.",
                "user": UserSerializer(user).data
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return Response({
                "status": "error",
                "code": "server_error",
                "message": "Internal server error during registration"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#Login API
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                "status": "error",
                "code": "invalid_input",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
            
            user = authenticate(
                request,
                email=email,
                password=password,
                backend='core_app.auth.EmailAuthBackend'
            )
            
            if user is None:
                User = get_user_model()
                try:
                    db_user = User.objects.get(email=email)
                    if not db_user.is_active:
                        return Response({
                            "status": "error",
                            "code": "account_inactive",
                            "message": "Account is inactive"
                        }, status=status.HTTP_403_FORBIDDEN)
                        
                    return Response({
                        "status": "error",
                        "code": "invalid_credentials",
                        "message": "Invalid password"
                    }, status=status.HTTP_401_UNAUTHORIZED)
                    
                except User.DoesNotExist:
                    return Response({
                        "status": "error",
                        "code": "user_not_found",
                        "message": "No user with this email exists"
                    }, status=status.HTTP_404_NOT_FOUND)

            access_token = generate_token(user.id, 'access')
            refresh_token = generate_token(user.id, 'refresh')
            
            return Response({
                "status": "success",
                "user": UserSerializer(user).data,
                "access_token": access_token,
                "refresh_token": refresh_token
            })
                
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return Response({
                "status": "error",
                "code": "server_error",
                "message": "Internal server error"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RefreshTokenView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        refresh_token = request.data.get('refresh_token')
        
        if not refresh_token:
            return Response({'error': 'Refresh token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            try:
                payload = verify_token(refresh_token)
                
                if payload.get('type') != 'refresh':
                    return Response({'error': 'Invalid token type - not a refresh token'}, 
                                    status=status.HTTP_400_BAD_REQUEST)
                
                user_id = payload.get('sub', payload.get('user_id'))
                if not user_id:
                    return Response({'error': 'Invalid token - no user ID'}, 
                                    status=status.HTTP_400_BAD_REQUEST)
                    
                access_token = generate_token(user_id, 'access')
                return Response({'access_token': access_token})
                
            except Exception as custom_error:
                from rest_framework_simplejwt.tokens import RefreshToken
                try:
                    refresh = RefreshToken(refresh_token)
                    return Response({
                        'access_token': str(refresh.access_token),
                    })
                except Exception:
                    raise custom_error
                
        except Exception as e:
            logger.error(f"Refresh token error: {str(e)}")
            return Response({'error': 'Invalid refresh token'}, status=status.HTTP_401_UNAUTHORIZED)

# Project API Views
class ProjectListCreateView(APIView):
    """List all projects the user is involved in, or create a new project."""
    def get(self, request, user_id=None):
        user = get_user_from_request(request)
        if not user:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        target_user = user  
        if user_id:
            try:
                target_user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            if not (user.is_staff or user.id == target_user.id):
                return Response({"error": "You don't have permission to view this user's projects"},
                                status=status.HTTP_403_FORBIDDEN)

        user_projects = UserProject.objects.filter(user=target_user).select_related('project')
        user_project_map = {up.project_id: up for up in user_projects}
        projects = [up.project for up in user_projects]

        response_data = []
        for project in projects:
            project_data = ProjectSerializer(project).data
            user_project = user_project_map.get(project.id)
            project_data['user_project_id'] = user_project.id if user_project else None
            project_data['role'] = user_project.role if user_project else None
            response_data.append(project_data)

        return Response(response_data)

    # def post(self, request):
    #     user = get_user_from_request(request)
    #     if not user or not user.is_staff:
    #         return Response({"error": "Only admin can create projects"}, status=status.HTTP_403_FORBIDDEN)

    #     data = request.data.copy()
    #     user_projects_data = data.pop('user_projects', [])
    #     owner_id = data.get('owner')

    #     if not owner_id:
    #         return Response({"error": "Missing 'owner' field"}, status=status.HTTP_400_BAD_REQUEST)

    #     try:
    #         owner = User.objects.get(id=owner_id)
    #     except User.DoesNotExist:
    #         return Response({"error": "Owner not found"}, status=status.HTTP_400_BAD_REQUEST)

    #     serializer = ProjectSerializer(data=data)
    #     if serializer.is_valid():
    #         with transaction.atomic():
    #             project = serializer.save(owner=owner)
    #             UserProject.objects.create(user=owner, project=project, role='owner')
    #             assigned_user_ids = {owner.id}

    #             for entry in user_projects_data:
    #                 try:
    #                     target_user = User.objects.get(id=entry['user'])
    #                     role = entry.get('role', 'collaborator')
    #                     if role in ['owner', 'collaborator'] and target_user.id not in assigned_user_ids:
    #                         UserProject.objects.create(user=target_user, project=project, role=role)
    #                         assigned_user_ids.add(target_user.id)
    #                 except User.DoesNotExist:
    #                     continue

    #         return Response(serializer.data, status=status.HTTP_201_CREATED)

    #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def post(self, request):
        user = get_user_from_request(request)
        if not user or not user.is_staff:
            return Response({"error": "Only admin can create or modify projects"}, status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        user_projects_data = data.pop('user_projects', [])
        owner_id = data.get('owner')
        project_name = data.get('name')

        if not owner_id:
            return Response({"error": "Missing 'owner' field"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            owner = User.objects.get(id=owner_id)
        except User.DoesNotExist:
            return Response({"error": "Owner not found"}, status=status.HTTP_400_BAD_REQUEST)
        existing_project = Project.objects.filter(name=project_name).first()

        if existing_project:
            added_users = []
            for entry in user_projects_data:
                try:
                    target_user = User.objects.get(id=entry['user'])
                    role = entry.get('role', 'collaborator')
                    if role in ['owner', 'collaborator']:
                        if not UserProject.objects.filter(user=target_user, project=existing_project).exists():
                            UserProject.objects.create(user=target_user, project=existing_project, role=role)
                            added_users.append(target_user.id)
                except User.DoesNotExist:
                    continue

            return Response({
                "message": f"Users added to existing project '{existing_project.name}'",
                "project_id": existing_project.id,
                "added_user_ids": added_users
            }, status=status.HTTP_200_OK)
        serializer = ProjectSerializer(data=data)
        if serializer.is_valid():
            with transaction.atomic():
                project = serializer.save(owner=owner)
                UserProject.objects.create(user=owner, project=project, role='owner')
                assigned_user_ids = {owner.id}

                for entry in user_projects_data:
                    try:
                        target_user = User.objects.get(id=entry['user'])
                        role = entry.get('role', 'collaborator')
                        if role in ['owner', 'collaborator'] and target_user.id not in assigned_user_ids:
                            UserProject.objects.create(user=target_user, project=project, role=role)
                            assigned_user_ids.add(target_user.id)
                    except User.DoesNotExist:
                        continue

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#projects API
class ProjectDetailView(APIView):
    """Retrieve, update, or delete a project instance"""
    def get_object(self, pk, user):
        try:
            project = Project.objects.get(pk=pk)
            if project.owner == user or UserProject.objects.filter(user=user, project=project).exists():
                return project
            return None
        except Project.DoesNotExist:
            return None
    
    def get(self, request, pk):
        user = get_user_from_request(request)
        if not user:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        project = self.get_object(pk, user)
        if not project:
            return Response({"error": "Project not found or access denied"}, 
                           status=status.HTTP_404_NOT_FOUND)
        return Response(ProjectSerializer(project).data)
    
    def patch(self, request, pk):
        user = get_user_from_request(request)
        if not user:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        project = self.get_object(pk, user)
        if not project:
            return Response({"error": "Project not found or access denied"}, 
                           status=status.HTTP_404_NOT_FOUND)
        if project.owner != user:
            return Response({"error": "Only the project owner can update project details"}, 
                           status=status.HTTP_403_FORBIDDEN)
            
        serializer = ProjectSerializer(project, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        user = get_user_from_request(request)
        if not user:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        project = self.get_object(pk, user)
        if not project:
            return Response({"error": "Project not found or access denied"}, 
                           status=status.HTTP_404_NOT_FOUND)
        if project.owner != user:
            return Response({"error": "Only the project owner can delete the project"}, 
                           status=status.HTTP_403_FORBIDDEN)
            
        project.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

# UserProject API Views
class UserProjectListCreateView(APIView):
    """List all user-project assignments or create a new assignment"""

    def get(self, request):
        user = get_user_from_request(request)
        if not user:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        project_id = request.query_params.get('project_id')
        user_id = request.query_params.get('user_id')
        owned_projects = Project.objects.filter(owner=user)
        queryset = UserProject.objects.filter(user=user) | UserProject.objects.filter(project__in=owned_projects)
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        queryset = queryset.distinct()
        serializer = UserProjectSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        user = get_user_from_request(request)
        if not user:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        project_id = request.data.get('project')
        try:
            project = Project.objects.get(id=project_id)
            if project.owner != user:
                return Response(
                    {"error": "Only the project owner can add users to this project"}, 
                    status=status.HTTP_403_FORBIDDEN
                )
        except Project.DoesNotExist:
            return Response({"error": "Project not found"}, status=status.HTTP_404_NOT_FOUND)
            
        serializer = UserProjectSerializer(data=request.data)
        if serializer.is_valid():
            user_project = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserProjectDetailView(APIView):
    """Retrieve, update, or delete a user-project assignment"""

    def get_object(self, pk, user):
        try:
            user_project = UserProject.objects.get(pk=pk)
            if user_project.user == user or user_project.project.owner == user:
                return user_project
            return None
        except UserProject.DoesNotExist:
            return None
    
    def get(self, request, pk):
        user = get_user_from_request(request)
        if not user:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        user_project = self.get_object(pk, user)
        if not user_project:
            return Response({"error": "User-Project assignment not found or access denied"}, 
                           status=status.HTTP_404_NOT_FOUND)
        
        return Response(UserProjectSerializer(user_project).data)
    
    def patch(self, request, pk):
        user = get_user_from_request(request)
        if not user:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        user_project = self.get_object(pk, user)
        if not user_project:
            return Response({"error": "User-Project assignment not found or access denied"}, 
                           status=status.HTTP_404_NOT_FOUND)
        
        if user_project.project.owner != user:
            return Response({"error": "Only the project owner can modify project assignments"}, 
                           status=status.HTTP_403_FORBIDDEN)
        
        if 'project' in request.data and request.data['project'] != user_project.project.id:
            return Response({"error": "Cannot change project association for an existing assignment"},
                          status=status.HTTP_400_BAD_REQUEST)
        
        serializer = UserProjectSerializer(user_project, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        user = get_user_from_request(request)
        if not user:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        user_project = self.get_object(pk, user)
        if not user_project:
            return Response({"error": "User-Project assignment not found or access denied"}, 
                           status=status.HTTP_404_NOT_FOUND)
        if user_project.project.owner != user:
            return Response({"error": "Only the project owner can remove users from the project"}, 
                           status=status.HTTP_403_FORBIDDEN)
            
        user_project.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

#Timesheet API
class TimesheetListCreateView(APIView):
    """List all timesheets or create a new timesheet"""
    def get(self, request):
        user = get_user_from_request(request)
        if not user:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        if user.is_staff or user.is_superuser:
            timesheets = Timesheet.objects.all()
        else:
            user_projects = UserProject.objects.filter(user=user)
            timesheets = Timesheet.objects.filter(user_project__in=user_projects)

        month_year = request.query_params.get('month_year')
        month = request.query_params.get('month')
        year = request.query_params.get('year')
        work_type = request.query_params.get('work_type')
        user_project_id = request.query_params.get('user_project')
        project_id = request.query_params.get('project_id') 

        if month_year:
            try:
                month, year = map(int, month_year.split('/'))
                timesheets = timesheets.filter(date__month=month, date__year=year)
            except (ValueError, AttributeError):
                pass
        elif month and year:
            try:
                month = int(month)
                year = int(year)
                timesheets = timesheets.filter(date__month=month, date__year=year)
            except ValueError:
                pass

        if user_project_id:
            timesheets = timesheets.filter(user_project_id=user_project_id)
        if project_id:
            timesheets = timesheets.filter(user_project__project_id=project_id)
        if work_type:
            timesheets = timesheets.filter(work_type=work_type)

        serializer = TimesheetSerializer(timesheets, many=True)
        raw_data = serializer.data

        total_duration = timesheets.aggregate(total=Sum('duration'))['total'] or 0
        leave_days = timesheets.annotate(
            leave_day_value=Case(
                When(work_type='full_day_leave', then=Value(1.0)),
                When(work_type='half_day_leave', then=Value(0.5)),
                default=Value(0.0),
                output_field=FloatField()
            )
        ).aggregate(total=Sum('leave_day_value'))['total'] or 0.0

        try:
            df = pd.DataFrame(raw_data)
            if not df.empty:
                df.rename(columns={
                    "project_name": "Project",
                    "date": "Date",
                    "description": "Description",
                    "duration": "Hours"
                }, inplace=True)

                validator = TimeValidator()
                validated_df = validator.validate(df)
                validated_data = validated_df.astype(str).to_dict(orient="records")
                summary_df = validator.create_summary({"Sheet1": validated_df})
                summary_data = summary_df.astype(str).to_dict(orient="records")
            else:
                validated_data = []
                summary_data = []

        except Exception as e:
            return Response({"error": "Validation failed", "details": str(e)}, status=500)
        today = date.today()
        if month and year:
            try:
                month = int(month)
                year = int(year)
                _, last_day = calendar.monthrange(year, month)
                start_date = date(year, month, 1)
                end_date = date(year, month, last_day)
                end_check_date = min(today, end_date)

                expected_dates = {
                    (start_date + timedelta(days=i)).isoformat()
                    for i in range((end_check_date - start_date).days + 1)
                    if (start_date + timedelta(days=i)).weekday() < 5  
                }

                existing_dates = {ts.get("date") for ts in raw_data}
                missing_dates = expected_dates - existing_dates

                for missed_date in sorted(missing_dates):
                    raw_data.append({
                        "date": missed_date,
                        "duration": 0,
                        "work_type": "working",
                        "Status": f"You missed this date {missed_date}.Please fill in the timesheet"
                    })
            except ValueError:
                pass     
        status_map = {
            (entry["Date"], entry["Hours"]): entry.get("Status", "")
            for entry in validated_data
        }

        for ts in raw_data:
            date_val = ts.get("date")
            hours = str(ts.get("duration", ""))
            if "Status" not in ts:
                ts["Status"] = status_map.get((date_val, hours), "")

        return Response({
            "timesheets": raw_data,
            "validated_data": validated_data,
            "validation_summary": summary_data,
            "statistics": {
                "total_duration": total_duration,
                "leave_days": leave_days
            }
        })

    def post(self, request):
        user = get_user_from_request(request)
        if not user:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        user_project_id = request.data.get('user_project')
        try:
            user_project = UserProject.objects.get(id=user_project_id)
            if user_project.user.id != user.id:
                return Response(
                    {"error": "You can only create timesheets for your own project assignments"},
                    status=status.HTTP_403_FORBIDDEN
                )
        except UserProject.DoesNotExist:
            return Response({"error": "User-Project assignment not found"},
                            status=status.HTTP_404_NOT_FOUND)

        serializer = TimesheetSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class TimesheetDetailView(APIView):
    """Retrieve, update, or delete a timesheet instance"""

    def get_object(self, pk, user):
        try:
            timesheet = Timesheet.objects.get(pk=pk)
            if timesheet.user_project.user == user or user.is_staff or user.is_superuser:
                return timesheet
            return None
        except Timesheet.DoesNotExist:
            return None

    def get(self, request, pk):
        user = get_user_from_request(request)
        if not user:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        timesheet = self.get_object(pk, user)
        if not timesheet:
            return Response({"error": "Timesheet not found or access denied"}, 
                            status=status.HTTP_404_NOT_FOUND)

        return Response(TimesheetSerializer(timesheet).data)

    def patch(self, request, pk):
        user = get_user_from_request(request)
        if not user:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        timesheet = self.get_object(pk, user)
        if not timesheet:
            return Response({"error": "Timesheet not found or access denied"}, 
                            status=status.HTTP_404_NOT_FOUND)

        user_project_id = request.data.get('user_project')
        if user_project_id:
            try:
                user_project = UserProject.objects.get(id=user_project_id)
                if not (user.is_staff or user.is_superuser) and user_project.user.id != user.id:
                    return Response(
                        {"error": "You can only assign timesheets to your own project assignments"}, 
                        status=status.HTTP_403_FORBIDDEN
                    )
            except UserProject.DoesNotExist:
                return Response({"error": "User-Project assignment not found"}, 
                                status=status.HTTP_404_NOT_FOUND)

        status_value = request.data.get("status")
        if status_value:
            if status_value.lower() == "half day":
                request.data["day_count"] = 0.5
            elif status_value.lower() == "leave":
                request.data["day_count"] = 1
            elif status_value.lower() == "present":
                request.data["day_count"] = 1

        serializer = TimesheetSerializer(timesheet, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        user = get_user_from_request(request)
        if not user:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        timesheet = self.get_object(pk, user)
        if not timesheet:
            return Response({"error": "Timesheet not found or access denied"}, 
                            status=status.HTTP_404_NOT_FOUND)

        timesheet.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class UserTimesheetListView(APIView):
    """Simple list of users with their projects and links to timesheets"""
    
    def get(self, request):
        requesting_user = get_user_from_request(request)
        if not requesting_user:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
        
        if requesting_user.is_staff:
            users = User.objects.filter(is_active=True).order_by('name')
            user_projects = UserProject.objects.all().select_related('project')
        else:
            users = User.objects.filter(id=requesting_user.id)
            user_projects = UserProject.objects.filter(user=requesting_user).select_related('project')
        
        response_data = []
        base_url = request.build_absolute_uri('/')[:-1] 
        
        for user in users:
            user_data = {
                'user_id': user.id,
                'user_name': user.name,
                'user_email': user.email,
                'projects': []
            }
            
            up_for_user = user_projects.filter(user=user)
            
            for up in up_for_user:
                project_data = {
                    'user_project_id': up.id, 
                    'project_id': up.project.id,
                    'project_name': up.project.name,
                    'role': up.role,
                    'timesheets_link': f"user-timesheet/{up.id}/{up.project.id}"  
                }
                user_data['projects'].append(project_data)
            
            response_data.append(user_data)
        
        if not requesting_user.is_staff and response_data:
            return Response(response_data[0])
        
        return Response(response_data)
        
class TimesheetAPIView(APIView):
    def get(self, request):
        user = request.user
        if not user.is_authenticated:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        timesheets = Timesheet.objects.all()
        if not user.is_staff:
            user_projects = UserProject.objects.filter(user=user)
            timesheets = timesheets.filter(user_project__in=user_projects)

        month_year = request.query_params.get("month_year")
        month = request.query_params.get("month")
        year = request.query_params.get("year")
        if month_year:
            try:
                month, year = map(int, month_year.split('/'))
                timesheets = timesheets.filter(date__month=month, date__year=year)
            except ValueError:
                return Response({"error": "Invalid 'month_year' format. Use MM/YYYY."}, status=400)
        elif month and year:
            try:
                timesheets = timesheets.filter(date__month=int(month), date__year=int(year))
            except ValueError:
                return Response({"error": "Invalid month/year."}, status=400)

        if 'project_id' in request.query_params:
            timesheets = timesheets.filter(user_project__project_id=request.query_params['project_id'])

        if 'work_type' in request.query_params:
            timesheets = timesheets.filter(work_type=request.query_params['work_type'])

        serializer = TimesheetSerializer(timesheets, many=True)
        timesheet_data = serializer.data

        total_duration = timesheets.aggregate(total=Sum('duration'))['total'] or 0
        leave_days = timesheets.annotate(
            leave_day_value=Case(
                When(work_type='full_day_leave', then=Value(1.0)),
                When(work_type='half_day_leave', then=Value(0.5)),
                default=Value(0.0),
                output_field=FloatField()
            )
        ).aggregate(total=Sum('leave_day_value'))['total'] or 0.0

        validated_records = []
        summary = []

        if timesheet_data:
            try:
                df = pd.DataFrame(timesheet_data)

                df.rename(columns={
                    "project_name": "Project",
                    "date": "Date",
                    "description": "Description",
                    "duration": "Hours"
                }, inplace=True)

                validator = TimeValidator()
                validated_df = validator.validate(df)
                summary_df = validator.create_summary({"Timesheet": validated_df})

                validated_records = validated_df.astype(str).to_dict(orient='records')
                summary = summary_df.astype(str).to_dict(orient='records')

            except Exception as e:
                return Response({"error": "Validation failed", "details": str(e)})
    
        return Response({
            "timesheets": timesheet_data,
            "validated_timesheets": validated_records,
            "validation_summary": summary,
            "statistics": {
                "total_duration": total_duration,
                "leave_days": leave_days
            }
        }, status=200)

#PPT Automation API  
class PPTAutomationAPI(APIView):
    def post(self, request):
        serializer = UploadExcelSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        output_path = os.path.join(settings.MEDIA_ROOT, 'Final_Anniversary_Presentation.pptx')
        
        try:
            excel_path = os.path.join(settings.MEDIA_ROOT, 'uploaded.xlsx')
            with open(excel_path, 'wb+') as destination:
                for chunk in request.FILES['file'].chunks():
                    destination.write(chunk)

            template_path = os.path.join(settings.MEDIA_ROOT, 'WorkAnniversaryLogo.pptx')
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            generate_presentation(
                template_path=template_path,
                excel_path=excel_path,
                output_path=output_path,
                user_name=data['name'],
                years_of_service=data['years']
            )
            return FileResponse(open(output_path, 'rb'), filename='Anniversary_Slides.pptx')
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Timesheet Automation API
class TimeTrackingAPI(APIView):  
    def setup_directories(self):
        """Setup required directories"""
        self.timesheet_dir = os.path.join(settings.MEDIA_ROOT, 'time_tracking')
        self.output_dir = os.path.join(settings.MEDIA_ROOT, 'time_tracking_outputs')
        self.archive_dir = os.path.join(settings.MEDIA_ROOT, 'time_tracking_archives')
        self.validation_dir = os.path.join(settings.MEDIA_ROOT, 'time_tracking_validations')
        
        for directory in [self.timesheet_dir, self.output_dir, self.archive_dir, self.validation_dir]:
            os.makedirs(directory, exist_ok=True)

    def post(self, request):
        serializer = UploadTimesheetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        self.setup_directories()
        validator = TimeValidator()
        output_manager = OutputManager(self.output_dir, self.archive_dir, self.validation_dir)

        try:
            timesheet_file = request.FILES['timesheet_file']
            timesheet_path = os.path.join(self.timesheet_dir, timesheet_file.name)
            with open(timesheet_path, 'wb+') as dest:
                for chunk in timesheet_file.chunks():
                    dest.write(chunk)

            validation_result = validator.run(timesheet_path)

            if not validation_result["success"]:
                return Response(
                    {'status': 'Invalid', 'flag': validation_result.get('error', 'Unknown error')},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Process validated sheets
            validated_sheets = {}
            for sheet_name, df in validation_result['validated_sheets'].items():
                processed_records = []
                for record in df.astype(str).to_dict(orient='records'):
                    status = "Valid"
                    flag = ""

                    # Check if Status column has issues
                    if "Status" in record and record["Status"] and record["Status"] not in ["OK", "Valid"]:
                        status = "Invalid"
                        flag = f"⚠ {record['Status']}"

                    record["Status"] = status
                    record["Flag"] = flag
                    processed_records.append(record)

                validated_sheets[sheet_name] = processed_records

            # Process summary data
            summary_data = []
            summary_df = validation_result['summary'].astype(str)
            for record in summary_df.to_dict(orient='records'):
                status = "Valid"
                flag = ""

                if "Status" in record and record["Status"] and record["Status"] not in ["OK", "Valid"]:
                    status = "Invalid"
                    flag = f"⚠ {record['Status']}"

                record["Status"] = status
                record["Flag"] = flag
                summary_data.append(record)

            validation_type = serializer.validated_data.get('validation_type', 'standard')
            validation_number = 1 if validation_type == 'custom' else None
            validated_file_path = output_manager.save_validated_data(validation_result, validation_number)

            if validated_file_path:
                zip_path = output_manager.create_zip_archive(validated_file_path)

            return Response({
                'file_name': timesheet_file.name,
                'validated_data': validated_sheets,
                'validation_summary': summary_data,
                'success': True
            })

        except Exception as e:
            return Response({
                'status': 'Invalid',
                'flag': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class TimeTrackingTemplateAPI(APIView): 
    def setup_directories(self):
        """Setup required directories"""
        self.output_dir = os.path.join(settings.MEDIA_ROOT, 'time_tracking_outputs')
        self.archive_dir = os.path.join(settings.MEDIA_ROOT, 'time_tracking_archives')
        self.validation_dir = os.path.join(settings.MEDIA_ROOT, 'time_tracking_validations')
        os.makedirs(self.output_dir, exist_ok=True)

    def post(self, request):
        serializer = GenerateTemplateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        self.setup_directories()
        output_manager = OutputManager(self.output_dir, self.archive_dir, self.validation_dir)
        
        try:
            month = serializer.validated_data.get('month')
            year = serializer.validated_data.get('year')
            
            template_path = output_manager.generate_monthly_template(month, year)
            
            if template_path and os.path.exists(template_path):
                return Response({
                    'success': True,
                    'template_path': os.path.basename(template_path),
                    'download_url': f'/api/time-tracking/templates/{os.path.basename(template_path)}/'
                })
            else:
                return Response(
                    {'success': False, 'error': 'Failed to generate template'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request, filename):
        """Download template"""
        template_path = os.path.join(settings.MEDIA_ROOT, 'time_tracking_outputs', filename)
        
        if os.path.exists(template_path):
            return FileResponse(open(template_path, 'rb'), filename=filename)
        else:
            return Response(
                {'error': 'Template file not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
class TimeTrackingEmailAPI(APIView):  
    def post(self, request):
        serializer = EmailSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        recipient_email = serializer.validated_data['recipient_email']
        json_data = serializer.validated_data['json_data']
        project = json_data.get('file_name', 'Unknown File')
        sender = request.user if request.user.is_authenticated else None
        recipient_user = User.objects.filter(email=recipient_email).first()

        try:
            email_sender = EmailSender()
            default_subject = f"Time Tracking Flags - {project}"

            success, flag_count = email_sender.send_flagged_data(
                recipient_email=recipient_email,
                subject=default_subject,
                json_data=json_data
            )

            TimesheetEmailLog.objects.create(
                recipient=recipient_user,
                project_name=project,
                status="Success" if success else "Email sending failed without exception",
                email_content=json_data,
                sent_by=sender
            )

            if success:
                return Response({
                    'success': True,
                    'message': f"Sent {flag_count} flagged entries to {recipient_email}"
                })
            else:
                return Response(
                    {'success': False, 'error': "Failed to send flagged entries"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        except Exception as e:
            TimesheetEmailLog.objects.create(
                recipient=recipient_user,
                project_name=project,
                status=str(e),
                email_content=json_data,
                sent_by=sender
            )
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RequestPasswordResetView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({"status": "error", "message": "Email is required"}, status=400)

        User = get_user_model()
        try:
            user = User.objects.get(email=email)
            token = generate_password_reset_token(user.id)

            reset_url = f"{settings.FRONTEND_BASE_URL}/reset-password?token={token}"
            email_body = f"""
            Hello {user.name or user.email},

            You requested a password reset. Please click the link below to reset your password:
            {reset_url}

            This link will expire in 1 hour.

            If you didn't request this, you can ignore this email.

            """ 

            msg = MIMEText(email_body)
            msg['Subject'] = "Password Reset Instructions"
            msg['From'] = settings.DEFAULT_FROM_EMAIL
            msg['To'] = user.email

            with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.sendmail(settings.DEFAULT_FROM_EMAIL, [user.email], msg.as_string())

            return Response({"status": "success", "message": "Password reset link sent to email", "reset_token": token})
        except User.DoesNotExist:
            return Response({"status": "error", "message": "User not found"}, status=404)
        except Exception as e:
            logger.error(f"[RESET_EMAIL_ERROR] {str(e)}")
            return Response({"status": "error", "message": f"Failed to send email: {str(e)}"}, status=500)

class ConfirmPasswordResetView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token')
        new_password = request.data.get('new_password')

        if not token or not new_password:
            return Response({"status": "error", "message": "Token and new password are required"}, status=400)

        try:
            user_id = verify_password_reset_token(token)
            User = get_user_model()
            user = User.objects.get(id=user_id)
            user.set_password(new_password)
            user.save()
            return Response({"status": "success", "message": "Password has been reset successfully"})
        except ValueError as e:
            return Response({"status": "error", "message": str(e)}, status=400)
        except User.DoesNotExist:
            return Response({"status": "error", "message": "User not found",}, status=404)
        
class ValidateMultipleTimesheetView(APIView):
    
    def get(self, request):
        requesting_user = get_user_from_request(request)
        if not requesting_user:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        month = request.query_params.get("month")
        year = request.query_params.get("year")
        if not month or not year:
            return Response({"error": "month and year are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            month = int(month)
            year = int(year)
        except ValueError:
            return Response({"error": "Invalid month or year format."}, status=status.HTTP_400_BAD_REQUEST)

        month_date = date(year, month, 1)

        if requesting_user.is_staff:
            users = User.objects.filter(is_active=True).order_by('name')
            user_projects = UserProject.objects.all().select_related('project')
        else:
            users = User.objects.filter(id=requesting_user.id)
            user_projects = UserProject.objects.filter(user=requesting_user).select_related('project')

        response_data = []

        for user in users:
            user_data = {
                'user_id': user.id,
                'user_name': user.name,
                'user_email': user.email,
                'projects': []
            }

            up_for_user = user_projects.filter(user=user)

            for up in up_for_user:
                project_id = up.project.id

                validation_logs = AutomationTimesheet.objects.filter(month=month_date).order_by('-updated_at')
                latest_log = None
                for log in validation_logs:
                    saved_map = log.result.get("user_project_map", {})
                    if str(user.id) in saved_map and project_id in saved_map[str(user.id)]:
                        latest_log = log
                        break

                validation_status = "Needs to be run"
                error_messages = ""
                timesheet_validations = []

                if latest_log:
                    validated_data = latest_log.result.get("validated_data", {})
                    user_key = str(user.id)
                    project_key = str(project_id)
                    user_projects_data = validated_data.get(user_key, {}).get(project_key, [])

                    actual_entries = Timesheet.objects.filter(
                        user_project=up,
                        date__year=year,
                        date__month=month
                    ).values('date', 'updated_at')

                    updated_map = {e['date']: e['updated_at'] for e in actual_entries}
                    actual_dates = set(updated_map.keys())

                    _, last_day = calendar.monthrange(year, month)
                    expected_dates = {
                        date(year, month, day)
                        for day in range(1, last_day + 1)
                        if date(year, month, day).weekday() < 5 
                    }

                    missing_dates = expected_dates - actual_dates

                    error_flags = []
                    has_changes = False

                    log_time = getattr(latest_log, 'updated_at', latest_log.created_at)
                    if is_naive(log_time):
                        log_time = make_aware(log_time, timezone=get_current_timezone())

                    for entry in user_projects_data:
                        entry_date = entry.get("Date") or entry.get("date")
                        entry_status = entry.get("Status")
                        flag = entry.get("Flag")

                        changed = False
                        if entry_date:
                            entry_dt = parse_date(entry_date)
                            ts_updated = updated_map.get(entry_dt)

                            if ts_updated:
                                if is_naive(ts_updated):
                                    ts_updated = make_aware(ts_updated, timezone=get_current_timezone())

                                if ts_updated > log_time:
                                    changed = True
                                    has_changes = True

                        timesheet_validations.append({
                            **entry,
                            "changed": changed
                        })

                        if entry_status == "Invalid" and flag:
                            error_flags.append(flag.strip())

                    if not user_projects_data:
                        summary = latest_log.result.get("validation_summary", {})
                        project_summaries = summary.get(user_key, {}).get(project_key, [])
                        for item in project_summaries:
                            if item.get("Status") == "Invalid" and "no timesheet" in item.get("Flag", "").lower():
                                timesheet_validations.append({
                                    "Flag": item["Flag"],
                                    "Status": item["Status"],
                                    "changed": False
                                })
                                error_flags.append(item["Flag"])

                    if actual_entries:
                        for missing_date in sorted(missing_dates):
                            timesheet_validations.append({
                                "Date": missing_date.isoformat(),
                                "Status": "Invalid",
                                "Flag": "Missing timesheet entry",
                                "changed": False
                            })
                        error_flags.append(f"Missing timesheet for {missing_date.isoformat()}")

                    if has_changes:
                        validation_status = "Needs rerun"
                    else:
                        validation_status = latest_log.result.get("status", "Success")

                    if error_flags:
                        error_messages = "\n".join(error_flags)

                project_data = {
                    'user_project_id': up.id,
                    'project_id': project_id,
                    'project_name': up.project.name,
                    'role': up.role,
                    'validation_status': validation_status,
                    'error': error_messages or None,
                    'timesheet_validations': timesheet_validations
                }

                user_data['projects'].append(project_data)

            response_data.append(user_data)

        return Response(response_data)

    def post(self, request):
        user = get_user_from_request(request)
        if not user or not (user.is_staff or user.is_superuser):
            return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

        user_project_map = request.data.get("user_project_map", {})
        month = request.data.get("month")
        year = request.data.get("year")

        if not user_project_map or not month or not year:
            return Response(
                {"error": "user_project_map, month, and year are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            month = int(month)
            year = int(year)
        except ValueError:
            return Response({"error": "Invalid month or year format."}, status=400)

        validated_data = defaultdict(lambda: defaultdict(list))
        validation_summary = defaultdict(lambda: defaultdict(list))
        missing_dates = defaultdict(dict)
        total_duration = 0
        total_leave_days = 0
        errors = []

        first_timesheet_id = None

        for uid, project_ids in user_project_map.items():
            for project_id in project_ids:
                try:
                    user_project_qs = UserProject.objects.filter(user_id=uid, project_id=project_id)
                    if not user_project_qs.exists():
                        validated_data[uid][project_id] = []
                        missing_dates[uid][project_id] = []
                        validation_summary[uid][project_id].append({
                            "Status": "Invalid",
                            "Flag": "⚠ User not assigned to this project.",
                            "user_id": uid,
                            "project_id": project_id
                        })
                        continue
                    timesheets = Timesheet.objects.filter(
                        user_project__in=user_project_qs,
                        date__month=month,
                        date__year=year
                    ).select_related("user_project__project")

                    if not timesheets.exists():
                        validation_summary[uid][project_id].append({
                            "Status": "Invalid",
                            "Flag": "⚠ No timesheets for this project.",
                            "user_id": uid,
                            "project_id": project_id
                        })
                        continue

                    serializer = TimesheetSerializer(timesheets, many=True)
                    raw_data = serializer.data
                    total_duration += sum(ts.duration for ts in timesheets)
                    leave_days = sum([
                        1.0 if ts.work_type == "full_day_leave" else 0.5 if ts.work_type == "half_day_leave" else 0.0
                        for ts in timesheets
                    ])
                    total_leave_days += leave_days

                    df = pd.DataFrame(raw_data)
                    if not df.empty:
                        df.rename(columns={
                            "project_name": "Project",
                            "date": "Date",
                            "description": "Description",
                            "duration": "Hours"
                        }, inplace=True)

                        validator = TimeValidator()
                        result = validator.validate_dataframe(df)

                        if result["success"]:
                            enriched_validated = []
                            for validated_row, raw_row in zip(result["validated_data"], raw_data):
                                ts_id = raw_row.get("id")
                                validated_row["timesheet_id"] = ts_id
                                if not first_timesheet_id:
                                    first_timesheet_id = ts_id

                                status_text = validated_row.get("Status", "")
                                validated_row["Status"] = "Valid" if status_text in ["", "OK", "Valid"] else "Invalid"
                                validated_row["Flag"] = "" if validated_row["Status"] == "Valid" else f"⚠ {status_text}"

                                enriched_validated.append(validated_row)

                            validated_data[uid][project_id].extend(enriched_validated)

                            for summary in result.get("summary_data", []):
                                s_status = summary.get("Status", "")
                                summary["Status"] = "Valid" if s_status in ["", "OK", "Valid"] else "Invalid"
                                summary["Flag"] = "" if summary["Status"] == "Valid" else f"⚠ {s_status}"
                                validation_summary[uid][project_id].append(summary)
                        else:
                            errors.append({
                                "user_id": uid,
                                "project_id": project_id,
                                "error": result["error"]
                            })
                            continue

                    today = date.today()
                    _, last_day = calendar.monthrange(year, month)
                    start_date = date(year, month, 1)
                    end_date = date(year, month, last_day)
                    end_check_date = min(today, end_date)

                    expected_dates = {
                        (start_date + timedelta(days=i)).isoformat()
                        for i in range((end_check_date - start_date).days + 1)
                        if (start_date + timedelta(days=i)).weekday() < 5
                    }

                    existing_dates = {ts.get("date") for ts in raw_data}
                    missing = sorted(expected_dates - existing_dates)
                    missing_dates[uid][project_id] = missing

                except Exception as e:
                    errors.append({
                        "user_id": uid,
                        "project_id": project_id,
                        "error": str(e)
                    })
                    continue

        has_validations = any(
            bool(projects) for user in validated_data.values() for projects in user.values()
        )

        if errors:
            overall_status = "Error"
        elif not has_validations:
            overall_status = "Needs to be run"
        else:
            overall_status = "Success"
        result_data = {
            "user_project_map": user_project_map,
            "validated_data": validated_data,
            "validation_summary": validation_summary,
            "statistics": {
                "total_duration": total_duration,
                "leave_days": total_leave_days
            },
            "missing_dates": missing_dates,
            "errors": errors
        }

        month_date = date(year, month, 1)
        normalized_input = normalize_dict(user_project_map)

        existing_logs = AutomationTimesheet.objects.filter(month=month_date)
        timesheet_number = None
        existing_log = None

        for log in existing_logs:
            saved_map = log.result.get("user_project_map")
            if saved_map and normalize_dict(saved_map) == normalized_input:
                existing_log = log
                timesheet_number = log.timesheet_number
                break

        if existing_log:
            old_validated_data = convert_decimals(existing_log.result.get("validated_data", {}))
            new_validated_data = convert_decimals(validated_data)

            if normalize_dict(old_validated_data) != normalize_dict(new_validated_data):
                overall_status = "Needs rerun"

        if not existing_log:
            last_log = AutomationTimesheet.objects.order_by("-timesheet_number").first()
            timesheet_number = (last_log.timesheet_number if last_log else 0) + 1
            try:
                AutomationTimesheet.objects.create(
                    timesheet_number=timesheet_number,
                    type=TimesheetType.MANUAL,
                    month=month_date,
                    status=overall_status,
                    result=convert_decimals(result_data)
                )
            except Exception as e:
                return Response({"error": f"Failed to save log: {str(e)}"}, status=500)
        else:
            try:
                existing_log.status = overall_status
                existing_log.result = convert_decimals(result_data)
                existing_log.save()
            except Exception as e:
                return Response({"error": f"Failed to update log: {str(e)}"}, status=500)
        result_data["status"] = overall_status
        return Response(result_data, status=200)

class PushTimesheetEmailView(APIView):
    def post(self, request):
        user = get_user_from_request(request)
        if not user or not (user.is_staff or user.is_superuser):
            return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

        user_project_map = request.data.get("user_project_map")
        month = request.data.get("month")
        year = request.data.get("year")

        if not user_project_map or not month or not year:
            return Response({"error": "user_project_map, month, and year are required."}, status=400)

        try:
            month = int(month)
            year = int(year)
        except ValueError:
            return Response({"error": "Month and year must be integers."}, status=400)

        month_date = date(year, month, 1)
        log = AutomationTimesheet.objects.filter(month=month_date, status='Success').order_by('-id').first()

        if not log:
            return Response({"error": "No validation log found for given month."}, status=404)

        full_result = log.result or {}
        validated_data = full_result.get("validated_data", {})

        if not validated_data:
            return Response({"error": "No validated data found in the automation log."}, status=404)

        email_sender = EmailSender()
        success_emails = []
        failed_emails = []

        for uid, project_ids in user_project_map.items():
            user = User.objects.filter(id=uid).first()
            if not user or not user.email:
                failed_emails.append(f"User ID {uid} has no valid email.")
                continue

            uid_str = str(uid)
            user_data = validated_data.get(uid_str, {})
            user_missing_data = full_result.get("missing_dates", {}).get(uid_str, {})

            for project_id in project_ids:
                project_id_str = str(project_id)

                sheet_data = user_data.get(project_id_str, [])
                missing_data = user_missing_data.get(project_id_str, [])

                if not sheet_data and not missing_data:
                    failed_emails.append(f"❌ No data found for User ID {uid}, Project ID {project_id}.")
                    continue

                json_data = {
                    "validated_data": sheet_data,
                    "missing_dates": missing_data,
                    "file_name": f"Project {project_id}"
                }

                success, count = email_sender.send_flagged_data(
                    recipient_email=user.email,
                    subject=f"Time Tracking Flags - Project {project_id}",
                    json_data=json_data
                )

                TimesheetEmailLog.objects.create(
                    recipient=user,
                    project_name=f"Project {project_id}",
                    status="Success" if success else "Failed",
                    email_content=json_data,
                    sent_by=request.user if request.user.is_authenticated else None
                )

                if success:
                    success_emails.append(f"✅ {user.email} - {count} issues")
                else:
                    failed_emails.append(f"❌ {user.email} - Send failed")

        return Response({
            "sent": success_emails,
            "failed": failed_emails,
        }, status=200 if not failed_emails else 207)


class ProjectUserRolesView(APIView):
    """Admin-only: Paginated project list with optional project name and user search filters."""

    def get(self, request):
        user = get_user_from_request(request)
        if not user or not (user.is_staff or user.is_superuser):
            return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

        project_search = request.query_params.get('project_search', '').strip()
        user_search = request.query_params.get('user_search', '').strip()

        try:
            page = max(1, int(request.query_params.get('page', 1)))
            page_size = min(50, max(1, int(request.query_params.get('page_size', 10))))
        except (ValueError, TypeError):
            page = 1
            page_size = 10

        projects = Project.objects.all().order_by('name')

        if project_search:
            projects = projects.filter(name__icontains=project_search)

        total_count = projects.count()
        total_pages = max(1, (total_count + page_size - 1) // page_size)
        page = min(page, total_pages)
        offset = (page - 1) * page_size
        projects = projects[offset: offset + page_size]

        results = []
        for project in projects:
            assignments = UserProject.objects.filter(project=project).select_related('user')
            if user_search:
                assignments = assignments.filter(
                    Q(user__name__icontains=user_search) |
                    Q(user__email__icontains=user_search) |
                    Q(role__icontains=user_search)
                )
            assignments = assignments.order_by('role', 'user__name')
            users = [
                {
                    "user_id": up.user.id,
                    "user_name": up.user.name,
                    "email": up.user.email,
                    "role": up.role,
                }
                for up in assignments
            ]
            results.append({
                "project_id": project.id,
                "project_name": project.name,
                "user_count": UserProject.objects.filter(project=project).count(),
                "users": users,
            })

        return Response({
            "count": total_count,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": page_size,
            "results": results,
        }, status=status.HTTP_200_OK)


class ProjectUsersView(APIView):
    """Admin-only: Paginated user list for a specific project with optional user search filter."""

    def get(self, request, project_id):
        user = get_user_from_request(request)
        if not user or not (user.is_staff or user.is_superuser):
            return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

        try:
            project = Project.objects.get(id=project_id)
        except Project.DoesNotExist:
            return Response({"error": "Project not found."}, status=status.HTTP_404_NOT_FOUND)

        user_search = request.query_params.get('user_search', '').strip()

        try:
            page = max(1, int(request.query_params.get('page', 1)))
            page_size = min(50, max(1, int(request.query_params.get('page_size', 12))))
        except (ValueError, TypeError):
            page = 1
            page_size = 12

        assignments = UserProject.objects.filter(project=project).select_related('user')
        if user_search:
            assignments = assignments.filter(
                Q(user__name__icontains=user_search) |
                Q(user__email__icontains=user_search) |
                Q(role__icontains=user_search)
            )
        assignments = assignments.order_by('role', 'user__name')

        total_count = assignments.count()
        total_pages = max(1, (total_count + page_size - 1) // page_size)
        page = min(page, total_pages)
        offset = (page - 1) * page_size
        assignments = assignments[offset: offset + page_size]

        users = [
            {
                "user_id": up.user.id,
                "user_name": up.user.name,
                "email": up.user.email,
                "role": up.role,
            }
            for up in assignments
        ]

        return Response({
            "project_id": project.id,
            "project_name": project.name,
            "count": total_count,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": page_size,
            "users": users,
        }, status=status.HTTP_200_OK)

