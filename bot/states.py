from aiogram.fsm.state import State, StatesGroup

class RegistrationStates(StatesGroup):
    waiting_game_id = State()
    waiting_nickname = State()

class MatchCreationStates(StatesGroup):
    waiting_lobby_url = State()
    waiting_match_info = State()
    waiting_confirmation = State()

class AdminStates(StatesGroup):
    add_hoster = State()
    confirm_add_hoster = State()
    remove_hoster = State()
    confirm_remove_hoster = State()
    add_role = State()
    remove_role = State()
    register_match_stats = State()
