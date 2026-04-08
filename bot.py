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

# ========== АДМИНИСТРАТОРЫ ==========
ADMIN_IDS = [1291472367]
# ====================================

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

# ========== ИНЛАЙН КНОПКИ ДЛЯ АДМИНА ==========
admin_actions_inline = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
    [InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_mailing")],
    [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
    [InlineKeyboardButton(text="🔄 Сброс статистики", callback_data="admin_reset_stats")],
    [InlineKeyboardButton(text="❌ Закрыть", callback_data="admin_close")]
])

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("🚫 У вас нет доступа")
        return
    await message.answer("👨‍💼 **Панель администратора**\n\nВыберите действие:", reply_markup=admin_actions_inline, parse_mode="Markdown")

@dp.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats_callback(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Нет доступа")
        return
    
    total = load_stats().get("total", {})
    
    report = (
        f"📊 **Статистика W0rkPlace**\n\n"
        f"📅 За всё время:\n"
        f"├ Начали диалог: {total.get('started', 0)}\n"
        f"├ Ответили на шаг 1: {total.get('step_1', 0)}\n"
        f"├ Указали город: {total.get('step_city', 0)}\n"
        f"├ Указали занятость: {total.get('step_hours', 0)}\n"
        f"├ Есть место: {total.get('step_place', 0)}\n"
        f"├ Устраивает загрузка: {total.get('step_load', 0)}\n"
        f"├ Аккуратные: {total.get('step_accuracy', 0)}\n"
        f"├ Задали вопросы: {total.get('asked_question', 0)}\n"
        f"├ Получили контакт отдела кадров: {total.get('got_hr_contact', 0)}\n"
        f"└ Отказов: {total.get('refused', 0)}\n\n"
        f"🎯 **Конверсия:** {round(total.get('got_hr_contact', 0) / total.get('started', 1) * 100, 1) if total.get('started', 0) > 0 else 0}%"
    )
    
    await callback.message.edit_text(report, reply_markup=admin_actions_inline, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "admin_mailing")
async def admin_mailing_callback(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Нет доступа")
        return
    
    await callback.message.edit_text(
        "📨 **Рассылка**\n\n"
        "Отправьте сообщение для рассылки всем пользователям.\n\n"
        "Для отмены отправьте /cancel",
        reply_markup=None,
        parse_mode="Markdown"
    )
    await callback.answer()
    await state.set_state("waiting_mailing_text")

@dp.callback_query(lambda c: c.data == "admin_users")
async def admin_users_callback(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Нет доступа")
        return
    
    stats = load_stats()
    users_count = len(stats.get("users", {}))
    
    users = stats.get("users", {})
    last_users = list(users.keys())[-10:] if users else []
    
    text = f"👥 **Пользователи**\n\nВсего: {users_count}\n\n"
    if last_users:
        text += "Последние 10:\n"
        for uid in reversed(last_users):
            user_info = users[uid].get("user_info", "нет данных")
            text += f"├ ID: `{uid}` - {user_info[:30]}\n"
    
    await callback.message.edit_text(text, reply_markup=admin_actions_inline, parse_mode="Markdown")
    await callback.answer()

# ========== СБРОС СТАТИСТИКИ ==========
@dp.callback_query(lambda c: c.data == "admin_reset_stats")
async def admin_reset_stats_callback(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Нет доступа")
        return
    
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ДА, сбросить", callback_data="reset_confirm")],
        [InlineKeyboardButton(text="❌ НЕТ, отмена", callback_data="reset_cancel")]
    ])
    
    await callback.message.edit_text(
        "⚠️ **ВНИМАНИЕ!**\n\nВы действительно хотите сбросить всю статистику?\n\nЭто действие необратимо.",
        reply_markup=confirm_keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "reset_confirm")
async def reset_confirm_callback(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Нет доступа")
        return
    
    stats = load_stats()
    stats["total"] = {
        "started": 0, "step_1": 0, "step_city": 0, "step_hours": 0,
        "step_place": 0, "step_load": 0, "step_accuracy": 0,
        "got_hr_contact": 0, "refused": 0, "asked_question": 0
    }
    save_stats(stats)
    
    await callback.message.edit_text(
        "✅ **Статистика успешно сброшена!**\n\nВсе счётчики обнулены.",
        reply_markup=admin_actions_inline,
        parse_mode="Markdown"
    )
    await callback.answer("Статистика сброшена")

@dp.callback_query(lambda c: c.data == "reset_cancel")
async def reset_cancel_callback(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("🚫 Нет доступа")
        return
    
    await callback.message.edit_text(
        "❌ Сброс статистики отменён.",
        reply_markup=admin_actions_inline,
        parse_mode="Markdown"
    )
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
    await message.answer("❌ Рассылка отменена.")

@dp.message(Command("answer"))
async def admin_answer(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("🚫 У вас нет доступа")
        return
    
    match = re.match(r'/answer\s+(\d+)\s+(.+)', message.text, re.DOTALL)
    if not match:
        await message.answer("❌ Неправильный формат. Используйте: `/answer ID Текст`", parse_mode="Markdown")
        return
    
    user_id = int(match.group(1))
    answer_text = match.group(2)
    
    try:
        await bot.send_message(
            user_id,
            f"📝 **Ответ от куратора:**\n\n{answer_text}\n\n---\n\n**А теперь ответьте, пожалуйста: готовы попробовать?**",
            reply_markup=final_keyboard
        )
        await message.answer(f"✅ Ответ отправлен пользователю {user_id}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# ========== КЛАВИАТУРЫ ==========
start_keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ Приступить")]], resize_keyboard=True)
place_keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ Да, есть")], [KeyboardButton(text="❌ Нет, негде")]], resize_keyboard=True)
load_keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ Да, устраивает")], [KeyboardButton(text="❌ Нет, мало/много")]], resize_keyboard=True)
accuracy_keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ Да, я аккуратный(ая)")], [KeyboardButton(text="❌ Нет, не уверен(а)")]], resize_keyboard=True)
final_keyboard = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ Да, готов(а) попробовать")], [KeyboardButton(text="❓ Есть вопросы")], [KeyboardButton(text="❌ Нет, не подходит")]], resize_keyboard=True)

class Form(StatesGroup):
    step_1 = State()
    step_city = State()
    step_hours = State()
    step_place = State()
    step_load = State()
    step_accuracy = State()
    step_faq = State()
    waiting_question = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or "без_username"
    
    update_stats(user_id, "started", username)
    
    await message.answer(
        "Здравствуйте!\n\n"
        "Я — ассистент по подбору персонала в компании W0rkPlace.\n\n"
        "Благодарю за проявленный интерес к вакансии «Упаковка/комплектация заказов на дому».\n\n"
        "Мы активно расширяемся и ищем новых сотрудников.\n\n"
        "Перед тем как я передам вас сотруднику, ответьте на пару вопросов.",
        reply_markup=start_keyboard
    )
    await state.set_state(Form.step_1)

@dp.message(Form.step_1, F.text == "✅ Приступить")
async def step_1_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    update_stats(user_id, "step_1")
    
    await message.answer(
        "📍 **В каком городе и районе вы проживаете?**\n\n"
        "Это нужно, чтобы понять, сможет ли курьер к вам приезжать.\n\n"
        "Напишите одним сообщением, например: *Москва, Южное Бутово*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(Form.step_city)

@dp.message(Form.step_city)
async def step_city_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    city = message.text
    await state.update_data(city=city)
    update_stats(user_id, "step_city", city)
    
    await message.answer(
        "⏰ **Сколько часов в день вы готовы уделять работе?**\n\n"
        "Например: *3-4 часа в день*, *только вечером*, *по выходным*",
        parse_mode="Markdown"
    )
    await state.set_state(Form.step_hours)

@dp.message(Form.step_hours)
async def step_hours_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    hours = message.text
    await state.update_data(hours=hours)
    update_stats(user_id, "step_hours", hours)
    
    await message.answer(
        "📦 **Есть ли у вас дома место для хранения товаров?**\n\n"
        "(стол, полка, угол комнаты — примерно 0.5-1 кв.м)",
        reply_markup=place_keyboard
    )
    await state.set_state(Form.step_place)

@dp.message(Form.step_place, F.text == "✅ Да, есть")
async def step_place_yes(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    update_stats(user_id, "step_place", "есть место")
    
    await message.answer(
        "📊 **Минимальный объём заказов за неделю — 50 штук (≈ 2-3 часа работы).**\n\n"
        "Вас это устраивает?",
        reply_markup=load_keyboard
    )
    await state.set_state(Form.step_load)

@dp.message(Form.step_place, F.text == "❌ Нет, негде")
async def step_place_no(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    update_stats(user_id, "refused")
    
    await message.answer(
        "К сожалению, для работы нужно небольшое место. Если появится — возвращайтесь! 👋",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()

@dp.message(Form.step_load, F.text == "✅ Да, устраивает")
async def step_load_yes(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    update_stats(user_id, "step_load", "устраивает")
    
    await message.answer(
        "⚠️ **Работа требует внимательности и аккуратности.**\n\n"
        "Вы готовы ответственно подходить к упаковке чужих товаров?",
        reply_markup=accuracy_keyboard
    )
    await state.set_state(Form.step_accuracy)

@dp.message(Form.step_load, F.text == "❌ Нет, мало/много")
async def step_load_no(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    update_stats(user_id, "refused")
    
    await message.answer(
        "Понимаем. Если передумаете — возвращайтесь. Удачи! 👋",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()

@dp.message(Form.step_accuracy, F.text == "✅ Да, я аккуратный(ая)")
async def step_accuracy_yes(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    update_stats(user_id, "step_accuracy", "аккуратный")
    
    faq_text = (
        "📋 **Вот ответы на часто задаваемые вопросы:**\n\n"
        "❓ **Нужен ли опыт?**\n"
        "Нет, процесс упаковки очень простой. Вы получаете готовые наборы с видео-инструкциями.\n\n"
        "❓ **С каким товаром работать?**\n"
        "Косметика, аксессуары, сувениры, игрушки — всё мелкое и лёгкое.\n\n"
        "❓ **Сколько платите?**\n"
        "50₽ за заказ. После 5 успешных сдач в срок и объёма от 500 заказов в месяц — 60₽.\n\n"
        "❓ **Как часто выплаты?**\n"
        "Еженедельно, по понедельникам.\n\n"
        "❓ **Какие сроки выполнения?**\n"
        "На 50-100 заказов — 2 дня.\n\n"
        "❓ **Кто платит за доставку?**\n"
        "Доставка к вам и обратно — за наш счёт.\n\n"
        "❓ **Сколько заказов даёте?**\n"
        "Первые 3 поставки — 50-100 заказов. С 4-й — 150-500.\n\n"
        "❓ **Что если не успел(а) в срок?**\n"
        "Учтём и дадим меньше. При регулярных задержках цена может снизиться до 45₽.\n\n"
        "⚠️ Работа требует внимательности и аккуратности.\n\n"
        "❓ **Готовы попробовать?**"
    )
    
    await message.answer(faq_text, reply_markup=final_keyboard)
    await state.set_state(Form.step_faq)

@dp.message(Form.step_accuracy, F.text == "❌ Нет, не уверен(а)")
async def step_accuracy_no(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    update_stats(user_id, "refused")
    
    await message.answer(
        "Спасибо за честность! Если измените мнение — возвращайтесь. 👋",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()

@dp.message(Form.step_faq, F.text == "✅ Да, готов(а) попробовать")
async def final_yes(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    user_info = f"{user_data.get('city', '')}, {user_data.get('hours', '')}"
    user_id = message.from_user.id
    username = message.from_user.username or "без_username"
    
    update_stats(user_id, "got_hr_contact")
    await notify_hr_contact(user_id, username, user_info)
    
    await message.answer(
        "🎉 **Отлично! Вы прошли первичный отбор.**\n\n"
        "Для дальнейшего трудоустройства свяжитесь с отделом кадров:\n\n"
        "📞 **@work_place_group**\n\n"
        "Напишите им слово **«Трудоустройство»**.\n\n"
        "👋 Всего доброго и удачи в работе!",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()

@dp.message(Form.step_faq, F.text == "❓ Есть вопросы")
async def final_question(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    update_stats(user_id, "asked_question")
    
    await message.answer(
        "📝 **Напишите ваш вопрос.** Я отвечу или передам куратору.\n\n"
        "После ответа мы продолжим.",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(Form.waiting_question)

@dp.message(Form.step_faq, F.text == "❌ Нет, не подходит")
async def final_no(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    user_info = f"{user_data.get('city', '')}, {user_data.get('hours', '')}"
    user_id = message.from_user.id
    username = message.from_user.username or "без_username"
    
    update_stats(user_id, "refused")
    await notify_refusal(user_id, username, user_info)
    
    await message.answer(
        "🙏 **Спасибо за честность!**\n\n"
        "Если в будущем передумаете или появятся вопросы — возвращайтесь.\n\n"
        "А пока вы можете уточнить детали вакансии напрямую в отделе кадров: @work_place_group\n\n"
        "🍀 **Удачи!**",
        reply_markup=ReplyKeyboardRemove()
    )
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
            await message.answer("🎉 **Отлично!**\n\n📞 @work_place_group\nНапишите «Трудоустройство»", reply_markup=ReplyKeyboardRemove())
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