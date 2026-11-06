from collections.abc import Mapping

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from jsonschema import ValidationError as SchemaValidationError

from arp_contracts.policy import validate_policy
from .models import Project, Role, User


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            raise serializers.ValidationError('Expected a JSON object.')
        if set(data) - set(self.fields):
            # Never echo untrusted field names or values (possibly credentials).
            raise serializers.ValidationError('Unknown fields are not accepted.')
        return super().to_internal_value(data)


class ProjectCreate(StrictSerializer):
    name = serializers.CharField(max_length=120)
    description = serializers.CharField(max_length=10000, required=False, allow_blank=True, default='')


class ProjectUpdate(StrictSerializer):
    expected_revision = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=120, required=False)
    description = serializers.CharField(max_length=10000, required=False, allow_blank=True)


class ProjectOutput(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'revision', 'created_at', 'updated_at']


class MembershipInput(StrictSerializer):
    expected_revision = serializers.IntegerField(min_value=0)
    roles = serializers.ListField(child=serializers.ChoiceField(choices=Role.choices), min_length=1, max_length=5)

    def validate_roles(self, value):
        if len(set(value)) != len(value):
            raise serializers.ValidationError('Duplicate roles are not accepted.')
        return value


class RevisionInput(StrictSerializer):
    expected_revision = serializers.IntegerField(min_value=1)


class ConfigInput(StrictSerializer):
    expected_revision = serializers.IntegerField(min_value=1)
    policy = serializers.JSONField()

    def validate_policy(self, value):
        try:
            return validate_policy(value)
        except SchemaValidationError:
            raise serializers.ValidationError('Policy does not match project-policy v1; AI stays disabled in P0.') from None


class UserCreate(StrictSerializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, max_length=1024, trim_whitespace=False)

    def validate(self, value):
        user = User(username=value['username'])
        try:
            user.full_clean(exclude=['password', 'last_login', 'date_joined'])
            validate_password(value['password'], user)
        except DjangoValidationError:
            raise serializers.ValidationError('Username is unavailable/invalid or password fails policy.') from None
        return value


class LoginInput(StrictSerializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=1024, trim_whitespace=False, write_only=True)
