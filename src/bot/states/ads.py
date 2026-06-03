from aiogram.fsm.state import StatesGroup, State

class AdCreation(StatesGroup):
    base_currency = State()   # Что отдаем (RUB, KRW, KZT)
    target_currency = State() # Что получаем
    rate = State()            # Курс
    min_limit = State()       # Минимальный порог сделки
    max_limit = State()       # Максимальный порог/Общий объем
    requisite = State()       # Выбор карты
    confirm = State()         # Финальное превью