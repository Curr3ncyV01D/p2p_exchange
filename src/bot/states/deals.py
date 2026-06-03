from aiogram.fsm.state import StatesGroup, State

class DealStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_requisite = State()
    waiting_for_receipt = State()        # Тейкер грузит чек
    waiting_for_receipt_maker = State()  # Мейкер грузит чек