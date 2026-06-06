from aiogram.fsm.state import StatesGroup, State

class VerificationStates(StatesGroup):
    active_verification = State() # В этом состоянии сообщения транслируются в топик админа
