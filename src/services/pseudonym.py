import random

def generate_nickname() -> str:
    adjectives = ["Быстрый", "Тихий", "Золотой", "Мудрый", "Смелый"]
    animals = ["Лев", "Орел", "Барс", "Кит", "Сокол"]
    return f"{random.choice(adjectives)} {random.choice(animals)} {random.randint(100, 999)}"