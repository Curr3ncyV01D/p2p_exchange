from aiogram import Router, F, types

router = Router()

@router.callback_query(F.data == "common_close")
async def process_close_message(callback: types.CallbackQuery):
    try:
        await callback.answer()
        await callback.message.delete()
    except Exception:
        await callback.answer("Сообщение уже удалено")