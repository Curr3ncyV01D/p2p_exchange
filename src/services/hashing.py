import secrets
import string

def generate_public_id(length: int = 6) -> str:
    """Генерирует короткий буквенно-цифровой код для объявления."""
    # Используем только заглавные буквы и цифры для удобства чтения
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))