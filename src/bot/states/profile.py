from aiogram.fsm.state import StatesGroup, State

class RequisiteStates(StatesGroup):
    waiting_for_bank_name = State()
    waiting_for_details = State()