import graphene # type: ignore
from myapp.models import *

# class RegistrationInputObject(graphene.InputObjectType):
#     username = graphene.String()
#     email = graphene.String(required=False)
#     password = graphene.String()
#     passwordConfirm = graphene.String()
#     role = graphene.String(required=False)
#     ward = graphene.String()
#     street = graphene.String()
#     sessionId = graphene.String(required=False)

class RegistrationInputObject(graphene.InputObjectType):
    username = graphene.String()
    email = graphene.String(required=False)
    password = graphene.String()
    passwordConfirm = graphene.String()
    role = graphene.String(required=False)
    
    ward = graphene.ID(required=False)    # changed from String to ID
    street = graphene.ID(required=False)  # changed from String to ID
    
    sessionId = graphene.String(required=False)



class RegistrationObject(graphene.ObjectType):
    id = graphene.ID()
    username = graphene.String()
    email = graphene.String()
    
class RegisterObject(graphene.ObjectType):
    id = graphene.ID()
    username = graphene.String()
    
class UserRegistrationInput(graphene.InputObjectType):
    username = graphene.String(required=True)
    password = graphene.String(required=True)
    passwordConfirm = graphene.String(required=True)
    
class UserRegistrationObject(graphene.ObjectType):
    id = graphene.ID()
    username = graphene.String()
    access_token = graphene.String()
    refresh_token = graphene.String()

class UserLoginInputObject(graphene.InputObjectType):
    username = graphene.String()
    password = graphene.String()

class UserLoginObject(graphene.ObjectType):
    id = graphene.ID()
    username = graphene.String()
    token = graphene.String()
    isStaff = graphene.Boolean()
    isWardExecutive = graphene.Boolean()
    isVillageChairman = graphene.Boolean()


class ReportInputObject(graphene.InputObjectType):
    description = graphene.String()
    email = graphene.String()
    district = graphene.String()
    date = graphene.String()

class ReportObject(graphene.ObjectType):
    description = graphene.String()
    email = graphene.String()
    district = graphene.String()
    date = graphene.String()
    
class OpenspaceInputObject(graphene.InputObjectType):
    name = graphene.String()
    latitude = graphene.Float()
    longitude = graphene.Float()
    district = graphene.String()
    street = graphene.String()
    shape_type = graphene.String(required=True)
    boundary = graphene.JSONString(required=True)
    area = graphene.Float(required=True)
    
class OpenspaceObject(graphene.ObjectType):
    id = graphene.ID()
    name = graphene.String()
    latitude = graphene.Float()
    longitude = graphene.Float()
    district = graphene.String()
    street = graphene.String()
    status = graphene.String()
    is_active = graphene.Boolean()
    shape_type = graphene.String()
    boundary = graphene.JSONString()
    area = graphene.Float()
    
class ToggleOpenspaceInput(graphene.InputObjectType):
    id = graphene.ID()
    is_active = graphene.Boolean()
    
class ReportInputObject(graphene.InputObjectType):
    description = graphene.String(required=True)
    email = graphene.String(required=False)
    session_id=graphene.String(required=True)
    file_path = graphene.String(required=False)
    
class ReportObject(graphene.ObjectType):
    description = graphene.String()
    email = graphene.String()
    fileUrl = graphene.String()

class HistoryObject(graphene.ObjectType):
    report_id = graphene.String()
    description = graphene.String()
    created_at = graphene.String()

class BookedOpenspaceObject(graphene.ObjectType):
    id = graphene.ID()
    username = graphene.String()
    date = graphene.String()
    duration = graphene.String()
    startdate = graphene.String()
    enddate = graphene.String()
    district = graphene.String()
    purpose = graphene.String()
    status = graphene.String()
    space_name = graphene.String()

    def resolve_space_name(self, info):
        return self.space.name if self.space else None
    
class UserObject(graphene.ObjectType):
    pk=graphene.ID()
    username=graphene.String()
    is_staff=graphene.Boolean()

class ProfileObject(graphene.ObjectType):
    id = graphene.ID(required=True)
    user=graphene.Field(UserObject)
    
class UserAllObject(graphene.ObjectType):
    pk = graphene.ID()
    username = graphene.String()
    email = graphene.String()
    ward = graphene.String()
    is_staff = graphene.Boolean()
    role = graphene.String()
