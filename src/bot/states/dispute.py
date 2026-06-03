from aiogram.fsm.state import StatesGroup, State

class DisputeStates(StatesGroup):
    waiting_for_reason = State()
    active_dispute = State() # В этом состоянии все сообщения летят админу