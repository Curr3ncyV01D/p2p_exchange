def format_number(value: float) -> str:
    """
    Превращает числа вида 12450.0 в '12 450' 
    (разделитель тысяч — пробел, без дробной части).
    """
    try:
        return f"{int(float(value)):,}".replace(",", " ")
    except (ValueError, TypeError):
        return str(value)
