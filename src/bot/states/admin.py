from aiogram.fsm.state import StatesGroup, State

class AdminStates(StatesGroup):
    waiting_for_search_query = State()
    waiting_for_ad_query = State()