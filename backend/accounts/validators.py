import re

from django.core.exceptions import ValidationError


PHONE_CHARACTERS = re.compile(r"^\+?[0-9(). -]+$")


def normalize_and_validate_phone(value):
    phone = value.strip()
    if not phone:
        return ""
    if not PHONE_CHARACTERS.fullmatch(phone):
        raise ValidationError("Enter a valid phone number.")
    digit_count = sum(character.isdigit() for character in phone)
    if digit_count < 7 or digit_count > 15:
        raise ValidationError("Enter a phone number containing 7 to 15 digits.")
    return phone
