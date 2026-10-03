"""Disable public account creation; operators are provisioned out of band."""

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class OperatorOnlyAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False


class OperatorOnlySocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        return False
