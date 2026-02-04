import asyncio
import aiohttp
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackData
from dotenv import load_dotenv
import os

load_dotenv()
BOT_TOKEN = "8473973624:AAF6WYUdZytkuNOQHKqEYnyNNAaocwCJ0cg"
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

class VinStates(StatesGroup):
    waiting_vin = State()

vin_cb = CallbackData("vin", "action", "vin", "cat")

@dp.message(Command("start"))
async def start(msg: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Проверить VIN", callback_data="vin_check")]
    ])
    await msg.answer("🚗 **VIN-Бот Запчастей**\n\n"
                    "Введите VIN (17 символов) для подбора:\n"
                    "*Z94C241BBLR142304*", 
                    reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "vin_check")
async def vin_check(callback):
    await callback.message.edit_text("📝 **Введите VIN номер:**\n`17 символов uppercase`", 
                                   parse_mode="Markdown")
    await VinStates.waiting_vin.set()

@dp.message(StateFilter(VinStates.waiting_vin))
async def process_vin(msg: types.Message, state: FSMContext):
    vin = re.sub(r'[^A-HJ-NPR-Z0-9]', '', msg.text.upper())
    
    if len(vin) != 17:
        return await msg.answer("❌ **Неверный VIN!**\n17 букв/цифр (без I,O,Q)")
    
    await msg.answer("🔄 **Ищу данные по VIN...**\n"
                    f"`{vin}`", parse_mode="Markdown")
    await state.update_data(vin=vin)
    
    # VIN декодер API (api-cloud.ru бесплатный)
    car_info = await decode_vin(vin)
    
    if car_info:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛢 Двигатель", callback_data=vin_cb.new("cat", vin, "engine"))],
            [InlineKeyboardButton(text="🔧 Трансмиссия", callback_data=vin_cb.new("cat", vin, "transmission"))],
            [InlineKeyboardButton(text="🧱 Подвеска", callback_data=vin_cb.new("cat", vin, "suspension"))],
            [InlineKeyboardButton(text="🛞 Тормоза", callback_data=vin_cb.new("cat", vin, "brakes"))]
        ])
        await msg.answer(f"✅ **{car_info['brand']} {car_info['model']}**\n"
                        f"*{car_info['year']}* | {car_info['engine']}\n"
                        f"КПП: {car_info.get('transmission', 'N/A')}\n"
                        f"Кузов: {car_info.get('body', 'N/A')}", 
                        reply_markup=kb, parse_mode="Markdown")
    else:
        await msg.answer("❌ Данные не найдены. Попробуйте другой VIN.")
    
    await state.clear()

async def decode_vin(vin: str) -> dict:
    """Бесплатный VIN декодер"""
    try:
        async with aiohttp.ClientSession() as session:
            # api-cloud.ru (500/день бесплатно)
            url = "https://api-cloud.ru/api/vindecoder.php"
            params = {
                'token': 'demo',  # Бесплатный
                'vin': vin
            }
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                if data.get('status') == 200 and data.get('found'):
                    report = data['reports'][0]
                    return {
                        'brand': report['vin']['mark'],
                        'model': report['vin']['model'],
                        'year': report['vin']['year'],
                        'engine': report['vin']['engine'],
                        'transmission': report['vin'].get('transmission'),
                        'body': report['vin'].get('bodytype')
                    }
    except:
        pass
    return None

@dp.callback_query(vin_cb.filter(F.action == "cat"))
async def show_category(callback: types.CallbackQuery, callback_ CallbackData, state: FSMContext):
    action, vin, cat = callback_data.action, callback_data.vin, callback_data.cat
    
    schemes = {
        "engine": ["Система ГРМ", "Цепь/ремень", "Масляный насос"],
        "transmission": ["АКПП", "МКПП", "Дивертер"],
        "suspension": ["Передняя подвеска", "Задняя подвеска"],
        "brakes": ["Передние тормоза", "Задние тормоза"]
    }
    
    kb = []
    for i, scheme in enumerate(schemes.get(cat, [])):
        kb.append([InlineKeyboardButton(text=f"📐 {scheme}", 
                                       callback_data=f"scheme_{vin}_{cat}_{i}")])
    kb.append([InlineKeyboardButton(text="⬅ Назад", callback_data="vin_check")])
    
    await callback.message.edit_text(f"🔧 **{cat.title()}**\n\nВыберите схему:",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("scheme_"))
async def show_scheme(callback: types.CallbackQuery):
    parts = [
        {"num": "1", "name": "Масляный фильтр", "oem": "7701473012", "analogs": ["2101012035", "8200294081"]},
        {"num": "2", "name": "Теплообменник", "oem": "8201063487", "analogs": ["VALEO 733926"]},
        {"num": "3", "name": "Датчик давления", "oem": "226B41000R", "analogs": ["FAE 38520"]}
    ]
    
    text = "📐 **Схема запчастей**\n\n"
    kb = []
    for part in parts:
        text += f"**{part['num']}** {part['name']}\n"
        kb.append([InlineKeyboardButton(text=f"{part['num']} ➤", 
                                       callback_data=f"part_{part['oem']}")])
    kb.append([InlineKeyboardButton(text="⬅ Схемы", callback_data="back_schemes")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("part_"))
async def show_part(callback: types.CallbackQuery):
    oem = callback.data.split("_")[1]
    analogs = ["2101012035", "8200294081", "WIX 51348"]
    
    text = f"🔧 **Деталь {oem}**\n\n✅ **Оригинал:** `{oem}`\n\n🔄 **Аналоги:**\n"
    for i, analog in enumerate(analogs, 1):
        text += f"{i}. `{analog}`\n"
    
    kb = [
        [InlineKeyboardButton(text="🛒 Exist.ru", url=f"https://www.exist.ru/search/?q={oem}")],
        [InlineKeyboardButton(text="🛒 Avto.pro", url=f"https://avto.pro/search/?q={oem}")],
        [InlineKeyboardButton(text="⬅ Схема", callback_data="back_scheme")]
    ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

if __name__ == "__main__":
    print("🚀 VIN-Бот запущен!")
    asyncio.run(dp.start_polling(bot))
