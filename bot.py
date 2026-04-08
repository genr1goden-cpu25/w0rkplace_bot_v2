import logging
import asyncio
import datetime
import json
import os
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

ADMIN_IDS = [1291472367]

STATS_FILE = "stats.json"

def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "users": {},
        "total": {
            "started": 0, "step_1": 0, "step_city": 0, "step_hours": 0,
            "step_place": 0, "step_load": 0, "step_accuracy": 0,
            "got_hr_contact": 0, "refused": 0, "asked_question": 0
        },
        "daily": {}
    }

def save_stats(stats):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

def update_stats(user_id: int, event: str, user_info: str = ""):
    stats = load_stats()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    if str(user_id) not in stats["users"]:
        stats["users"][str(user_id)] = {
            "first_seen": today,
            "last_seen": today,
            "events": [],
            "user_info": ""
        }
    else:
        stats["users"][str(user_id)]["last_seen"] = today
    
    stats["users"][str(user_id)]["events"].append({
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event": event,
        "info": user_info
    })
    
    if user_info and not stats["users"][str(user_id)]["user_info"]:
        stats["users"][str(user_id)]["user_info"] = user_info[:200]
    
    if event in stats["total"]:
        stats["total"][event] += 1
    
    if today not in stats["daily"]:
        stats["daily"][today] = {
            "started": 0, "step_1": 0, "step_city": 0, "step_hours": 0,
            "step_place": 0, "step_load": 0, "step_accuracy": 0,
            "got_hr_contact": 0, "refused": 0, "asked_question": 0
        }
    if event in stats["daily"][today]:
        stats["daily"][today][event] += 1
    
    save_stats(stats)

async def notify_hr_contact(user_id: int, username: str, user_info: str):
    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"✅ НОВЫЙ КАНДИДАТ!\n📝 {user_info}\n👤 @{username}")

async def notify_refusal(user_id: int, username: str, user_info: str):
    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"❌ ОТКАЗ\n📝 {user_info}\n👤 @{username}")

async def notify_question(user_id: int, username: str, user_info: str, question: str):
    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"❓ ВОПРОС\n👤 @{username}\n💬 {question}\n\n/answer {user_id}")

admin_actions_inline = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
    [InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_mailing")],
    [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
    [InlineKeyboardButton(text="❌ Закрыть", callback_data="admin_close")]
])

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("🚫 Нет доступа")
        return
    await message.answer("👨‍💼 Панель администратора\n\nВыберите действие:", reply_markup=admin_actions_inline)

@dp.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats_callback(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Нет доступа")
        return
    total = load_stats().get("total", {})
    report = (f"📊 Статистика:\nНачали: {total.get('started',0)}\nШаг1: {total.get('step_1',0)}\n"
              f"Город: {total.get('step_city',0)}\nЧасы: {total.get('step_hours',0)}\n"
              f"Место: {total.get('step_place',0)}\nЗагрузка: {total.get('step_load',0)}\n"
              f"Аккурат: {total.get('step_accuracy',0)}\nВопросы: {total.get('asked_question',0)}\n"
              f"ОК: {total.get('got_hr_contact',0)}\nОтказы: {total.get('refused',0)}\n\n"
              f"Конверсия: {round(total.get('got_hr_contact',0)/max(total.get('started',1),1)*100,1)}%")
    await callback.message.edit_text(report, reply_markup=admin_actions_inline)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_mailing")
async def admin_mailing_callback(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Нет доступа")
        return
    await callback.message.edit_text("📨 Рассылка\n\nОтправьте сообщение для рассылки.\nДля отмены /cancel")
    await callback.answer()
    await state.set_state("waiting_mailing_text")

@dp.callback_query(lambda c: c.data == "admin_users")
async def admin_users_callback(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Нет доступа")
        return
    stats = load_stats()
    users = stats.get("users", {})
    text = f"👥 Пользователи: {len(users)}\n\nПоследние 10:\n"
    for uid in list(users.keys())[-10:]:
        info = users[uid].get("user_info", "нет данных")[:30]
        text += f"├ {uid} - {info}\n"
    await callback.message.edit_text(text, reply_markup=admin_actions_inline)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_close")
async def admin_close_callback(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Нет доступа")
        return
    await callback.message.delete()
    await callback.answer()

@dp.message(Command("cancel"))
async def cancel_mailing(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено")

# ========== ИСПРАВЛЕННАЯ ФУНКЦИЯ С КНОПКАМИ ==========
@dp.message(Command("answer"))
async def admin_answer(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("🚫 У вас нет доступа")
        return
    
    match = re.match(r'/answer\s+(\d+)\s+(.+)', message.text, re.DOTALL)
    if not match:
        await message.answer("❌ /answer ID Текст")
        return
    
    user_id = int(match.group(1))
    answer_text = match.group(2)
    
    try:
        await bot.send_message(
            user_id,
            f"📝 **Ответ от куратора:**\n\n{answer_text}\n\n---\n\n**А теперь ответьте, пожалуйста: готовы попробовать?**",
            reply_markup=final_keyboard
        )
        await message.answer(f"✅ Ответ отправлен")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
# ===================================================

start_keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ Приступить")]], resize_keyboard=True)
place_keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ Да, есть")], [KeyboardButton(text="❌ Нет, негде")]], resize_keyboard=True)
load_keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ Да, устраивает")], [KeyboardButton(text="❌ Нет, мало/много")]], resize_keyboard=True)
accuracy_keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ Да, я аккуратный(ая)")], [KeyboardButton(text="❌ Нет, не уверен(а)")]], resize_keyboard=True)
final_keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ Да, готов(а) попробовать")], [KeyboardButton(text="❓ Есть вопросы")], [KeyboardButton(text="❌ Нет, не подходит")]], resize_keyboard=True)

class Form(StatesGroup):
    step_1 = State(); step_city = State(); step_hours = State(); step_place = State()
    step_load = State(); step_accuracy = State(); step_faq = State(); waiting_question = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    update_stats(message.from_user.id, "started", message.from_user.username or "no")
    await message.answer("Здравствуйте! Я ассистент W0rkPlace.\n\nОтветьте на пару вопросов.", reply_markup=start_keyboard)
    await state.set_state(Form.step_1)

@dp.message(Form.step_1, F.text == "✅ Приступить")
async def s1(message: types.Message, state: FSMContext):
    update_stats(message.from_user.id, "step_1")
    await message.answer("📍 Город и район?", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Form.step_city)

@dp.message(Form.step_city)
async def s2(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text)
    update_stats(message.from_user.id, "step_city", message.text)
    await message.answer("⏰ Сколько часов в день?")
    await state.set_state(Form.step_hours)

@dp.message(Form.step_hours)
async def s3(message: types.Message, state: FSMContext):
    await state.update_data(hours=message.text)
    update_stats(message.from_user.id, "step_hours", message.text)
    await message.answer("📦 Есть место для хранения?", reply_markup=place_keyboard)
    await state.set_state(Form.step_place)

@dp.message(Form.step_place, F.text == "✅ Да, есть")
async def s4_yes(message: types.Message, state: FSMContext):
    update_stats(message.from_user.id, "step_place", "есть")
    await message.answer("📊 50 заказов в неделю. Устраивает?", reply_markup=load_keyboard)
    await state.set_state(Form.step_load)

@dp.message(Form.step_place, F.text == "❌ Нет, негде")
async def s4_no(message: types.Message, state: FSMContext):
    update_stats(message.from_user.id, "refused")
    await message.answer("Жаль! Если появится место - возвращайтесь.", reply_markup=ReplyKeyboardRemove())
    await state.clear()

@dp.message(Form.step_load, F.text == "✅ Да, устраивает")
async def s5_yes(message: types.Message, state: FSMContext):
    update_stats(message.from_user.id, "step_load", "да")
    await message.answer("⚠️ Готовы ответственно подходить к работе?", reply_markup=accuracy_keyboard)
    await state.set_state(Form.step_accuracy)

@dp.message(Form.step_load, F.text == "❌ Нет, мало/много")
async def s5_no(message: types.Message, state: FSMContext):
    update_stats(message.from_user.id, "refused")
    await message.answer("Понимаем. Удачи!", reply_markup=ReplyKeyboardRemove())
    await state.clear()

@dp.message(Form.step_accuracy, F.text == "✅ Да, я аккуратный(ая)")
async def s6_yes(message: types.Message, state: FSMContext):
    update_stats(message.from_user.id, "step_accuracy", "да")
    await message.answer("💰 50₽ за заказ\n📦 Доставка бесплатно\n\n❓ **Готовы попробовать?**", reply_markup=final_keyboard)
    await state.set_state(Form.step_faq)

@dp.message(Form.step_accuracy, F.text == "❌ Нет, не уверен(а)")
async def s6_no(message: types.Message, state: FSMContext):
    update_stats(message.from_user.id, "refused")
    await message.answer("Спасибо за честность!", reply_markup=ReplyKeyboardRemove())
    await state.clear()

@dp.message(Form.step_faq, F.text == "✅ Да, готов(а) попробовать")
async def final_yes(message: types.Message, state: FSMContext):
    data = await state.get_data()
    update_stats(message.from_user.id, "got_hr_contact")
    await notify_hr_contact(message.from_user.id, message.from_user.username or "no", f"{data.get('city','')}, {data.get('hours','')}")
    await message.answer("🎉 **Отлично!**\n\n📞 @work_place_group\nНапишите «Трудоустройство»", reply_markup=ReplyKeyboardRemove())
    await state.clear()

@dp.message(Form.step_faq, F.text == "❓ Есть вопросы")
async def final_question(message: types.Message, state: FSMContext):
    update_stats(message.from_user.id, "asked_question")
    await message.answer("📝 Напишите ваш вопрос:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Form.waiting_question)

@dp.message(Form.step_faq, F.text == "❌ Нет, не подходит")
async def final_no(message: types.Message, state: FSMContext):
    data = await state.get_data()
    update_stats(message.from_user.id, "refused")
    await notify_refusal(message.from_user.id, message.from_user.username or "no", f"{data.get('city','')}, {data.get('hours','')}")
    await message.answer("🙏 Спасибо! Удачи!", reply_markup=ReplyKeyboardRemove())
    await state.clear()

@dp.message(Form.waiting_question)
async def handle_question(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text
    
    if text in ["✅ Да, готов(а) попробовать", "❓ Есть вопросы", "❌ Нет, не подходит"]:
        if text == "✅ Да, готов(а) попробовать":
            data = await state.get_data()
            update_stats(user_id, "got_hr_contact")
            await notify_hr_contact(user_id, message.from_user.username or "no", f"{data.get('city','')}, {data.get('hours','')}")
            await message.answer("🎉 **Отлично!**\n\n📞 @work_place_group", reply_markup=ReplyKeyboardRemove())
            await state.clear()
        elif text == "❓ Есть вопросы":
            update_stats(user_id, "asked_question")
            await message.answer("📝 Напишите ваш вопрос:", reply_markup=ReplyKeyboardRemove())
        elif text == "❌ Нет, не подходит":
            data = await state.get_data()
            update_stats(user_id, "refused")
            await notify_refusal(user_id, message.from_user.username or "no", f"{data.get('city','')}, {data.get('hours','')}")
            await message.answer("🙏 Спасибо! Удачи!", reply_markup=ReplyKeyboardRemove())
            await state.clear()
        return
    
    data = await state.get_data()
    update_stats(user_id, "asked_question")
    await notify_question(user_id, message.from_user.username or "no", f"{data.get('city','')}, {data.get('hours','')}", text)
    await message.answer("✅ Вопрос передан куратору. Ответ придёт сюда.", reply_markup=ReplyKeyboardRemove())

@dp.message(StateFilter("waiting_mailing_text"))
async def process_mailing(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await state.clear()
        return
    users = load_stats().get("users", {})
    success = 0
    await message.answer(f"📨 Рассылка {len(users)} пользователям...")
    for user_id in users.keys():
        try:
            await bot.send_message(int(user_id), f"📢 **Рассылка:**\n\n{message.text}")
            success += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await message.answer(f"✅ Готово! Отправлено: {success}")
    await state.clear()

async def main():
    print("🚀 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())