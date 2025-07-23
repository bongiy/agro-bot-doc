from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from db import Session, Field

router = Router()

class AddFieldState(StatesGroup):
    waiting_for_name = State()
    waiting_for_area = State()

@router.message(commands=["add_field"])
async def cmd_add_field(message: types.Message, state: FSMContext):
    await message.answer("Введіть назву поля:")
    await state.set_state(AddFieldState.waiting_for_name)

@router.message(AddFieldState.waiting_for_name)
async def field_name_entered(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Введіть фактичну площу поля, га:")
    await state.set_state(AddFieldState.waiting_for_area)

@router.message(AddFieldState.waiting_for_area)
async def field_area_entered(message: types.Message, state: FSMContext):
    data = await state.get_data()
    name = data["name"]
    try:
        area = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Некоректне число. Введіть площу ще раз:")
        return
    session = Session()
    field = Field(name=name, area_actual=area)
    session.add(field)
    session.commit()
    await message.answer(f"Поле “{name}” ({area:.4f} га) додано.")
    await state.clear()

@router.message(commands=["fields"])
async def list_fields(message: types.Message):
    session = Session()
    fields = session.query(Field).all()
    if not fields:
        await message.answer("Поля ще не створені.")
        return
    text = "\n".join([f"{fld.id}. {fld.name} — {fld.area_actual:.4f} га" for fld in fields])
    await message.answer(f"Список полів:\n{text}")
