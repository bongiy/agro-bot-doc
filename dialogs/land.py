from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from db import Session, LandPlot, Field

router = Router()

class AddLandState(StatesGroup):
    waiting_for_cadaster = State()
    waiting_for_area = State()
    waiting_for_ngo = State()
    waiting_for_field = State()

@router.message(commands=["add_land"])
async def cmd_add_land(message: types.Message, state: FSMContext):
    await message.answer("Введіть кадастровий номер ділянки (19 цифр):")
    await state.set_state(AddLandState.waiting_for_cadaster)

@router.message(AddLandState.waiting_for_cadaster)
async def land_cadaster_entered(message: types.Message, state: FSMContext):
    cad = message.text.strip()
    # простий контроль довжини, можна додати форматування
    if len(cad.replace(":", "")) != 19:
        await message.answer("Кадастровий номер має містити 19 цифр. Спробуйте ще раз.")
        return
    await state.update_data(cadaster=cad)
    await message.answer("Введіть площу ділянки, га:")
    await state.set_state(AddLandState.waiting_for_area)

@router.message(AddLandState.waiting_for_area)
async def land_area_entered(message: types.Message, state: FSMContext):
    try:
        area = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Некоректне число. Введіть площу ще раз:")
        return
    await state.update_data(area=area)
    await message.answer("Введіть НГО (можна пропустити):")
    await state.set_state(AddLandState.waiting_for_ngo)

@router.message(AddLandState.waiting_for_ngo)
async def land_ngo_entered(message: types.Message, state: FSMContext):
    try:
        ngo = float(message.text.replace(",", "."))
    except ValueError:
        ngo = None
    await state.update_data(ngo=ngo)
    # вибір поля (всі з БД)
    session = Session()
    fields = session.query(Field).all()
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for f in fields:
        kb.add(f"{f.id}: {f.name}")
    await state.update_data(fields={f"{f.id}: {f.name}": f.id for f in fields})
    await message.answer("Оберіть поле для ділянки:", reply_markup=kb)
    await state.set_state(AddLandState.waiting_for_field)

@router.message(AddLandState.waiting_for_field)
async def land_field_chosen(message: types.Message, state: FSMContext):
    data = await state.get_data()
    fields_dict = data.get("fields", {})
    field_id = fields_dict.get(message.text)
    if not field_id:
        await message.answer("Оберіть поле зі списку (натиснувши на кнопку):")
        return
    # Зберігаємо ділянку
    session = Session()
    plot = LandPlot(
        cadaster=data["cadaster"],
        area=data["area"],
        ngo=data.get("ngo"),
        field_id=field_id
    )
    session.add(plot)
    session.commit()
    await message.answer("Ділянка додана!", reply_markup=types.ReplyKeyboardRemove())
    await state.clear()
