import os
import logging
from logging.handlers import RotatingFileHandler
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from utils import AIAccountantCore
from dotenv import load_dotenv
import asyncio
from datetime import datetime

# Настройка логирования
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    file_handler = RotatingFileHandler(
        'bot.log',
        maxBytes=2*1024*1024,  # 2 MB
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

setup_logging()
logger = logging.getLogger(__name__)

# Инициализация
load_dotenv()
accountant = AIAccountantCore()

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"), parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Состояния
class Form(StatesGroup):
    waiting_income = State()
    waiting_doc_data = State()
    waiting_question = State()
    waiting_excel = State()

# Клавиатуры
def get_main_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("🧮 Налоговый калькулятор"))
    kb.add(KeyboardButton("📝 Генератор документов"))
    kb.add(KeyboardButton("💡 Консультация ИИ"))
    kb.add(KeyboardButton("📊 Анализ данных"))
    return kb

def get_tax_types_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("УСН 6%", callback_data="tax_usn6"))
    kb.add(InlineKeyboardButton("УСН 15%", callback_data="tax_usn15"))
    kb.add(InlineKeyboardButton("НДФЛ", callback_data="tax_ndfl"))
    return kb

# Обработчики команд
@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    await message.answer(
        "🤖 <b>Профессиональный бухгалтерский помощник</b>\n\n"
        "Я могу:\n"
        "• Рассчитать налоги\n"
        "• Генерировать документы\n"
        "• Консультировать по бухгалтерии\n"
        "• Анализировать финансовые данные",
        reply_markup=get_main_kb()
    )

@dp.message_handler(text="🧮 Налоговый калькулятор")
async def tax_start(message: types.Message):
    await Form.waiting_income.set()
    await message.answer(
        "Введите сумму дохода:",
        reply_markup=get_tax_types_kb()
    )

@dp.message_handler(state=Form.waiting_income)
async def process_income(message: types.Message, state: FSMContext):
    try:
        tax_data = accountant.calculate_tax(message.text, "УСН")
        
        response = (
            f"📊 <b>Налоговый расчет</b>\n\n"
            f"• Система: {tax_data['system']}\n"
            f"• Доход: {tax_data['income']:,.2f} ₽\n"
            f"• Ставка: {tax_data['rate']*100}%\n"
            f"• Налог к уплате: {tax_data['tax']:,.2f} ₽\n\n"
            f"⏰ Срок уплаты: {tax_data['deadline']}\n"
            f"📝 Формы: {', '.join(tax_data['forms'])}"
        )
        
        await message.answer(response)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
    finally:
        await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith('tax_'))
async def process_tax_type(callback: types.CallbackQuery):
    tax_type = callback.data.split('_')[1]
    await bot.answer_callback_query(callback.id)
    await bot.send_message(
        callback.from_user.id,
        f"Выбрана система: {tax_type.upper()}. Введите сумму дохода:"
    )

@dp.message_handler(text="📝 Генератор документов")
async def doc_start(message: types.Message):
    await Form.waiting_doc_data.set()
    await message.answer(
        "Введите данные для договора в формате:\n"
        "<code>Клиент, Сумма, Услуга</code>\n\n"
        "Пример:\n<code>ООО Ромашка, 50000, Бухгалтерское сопровождение</code>"
    )

@dp.message_handler(state=Form.waiting_doc_data)
async def process_doc(message: types.Message, state: FSMContext):
    try:
        data = [x.strip() for x in message.text.split(',')]
        if len(data) != 3:
            raise ValueError("Неверный формат данных")
            
        client, amount, service = data
        filename = await accountant.generate_document(
            "Договор",
            client=client,
            amount=float(amount),
            service=service
        )
        
        with open(filename, 'rb') as doc:
            await message.answer_document(
                doc,
                caption=f"✅ Договор для {client} готов!\n\n"
                       f"Услуга: {service}\n"
                       f"Сумма: {float(amount):,.2f} ₽"
            )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
    finally:
        await state.finish()

@dp.message_handler(text="💡 Консультация ИИ")
async def ai_consult(message: types.Message):
    await Form.waiting_question.set()
    await message.answer(
        "Задайте ваш профессиональный вопрос бухгалтеру-ИИ:\n\n"
        "Примеры:\n"
        "• Как учесть командировочные расходы?\n"
        "• Какие документы нужны для возврата НДС?\n"
        "• Как перейти на УСН с ОСНО?"
    )

@dp.message_handler(state=Form.waiting_question)
async def process_question(message: types.Message, state: FSMContext):
    await message.answer_chat_action("typing")
    
    try:
        # Быстрые ответы для частых вопросов
        quick_responses = {
            "срок уплаты ндс": "До 25 числа следующего месяца (ст. 174 НК РФ)",
            "ставка ндфл": "13% для резидентов, 30% для нерезидентов (ст. 224 НК РФ)",
            "усн": "Упрощенная система налогообложения (6% или 15%) - НК РФ ст. 346.12"
        }
        
        prompt_lower = message.text.lower()
        for question, answer in quick_responses.items():
            if question in prompt_lower:
                await message.answer(answer)
                return
                
        response = await accountant.ask_ai(message.text)
        await message.answer(response[:4000])
    except Exception as e:
        await message.answer(f"⚠️ Ошибка: {str(e)}")
    finally:
        await state.finish()

@dp.message_handler(text="📊 Анализ данных")
async def data_analysis_start(message: types.Message):
    await Form.waiting_excel.set()
    await message.answer("Отправьте Excel-файл с финансовыми данными для анализа")

@dp.message_handler(content_types=['document'], state=Form.waiting_excel)
async def process_excel(message: types.Message, state: FSMContext):
    try:
        file_id = message.document.file_id
        file = await bot.get_file(file_id)
        file_path = f"temp_{datetime.now().strftime('%Y%m%d')}.xlsx"
        
        await message.document.download(destination_file=file_path)
        analysis = accountant.analyze_excel(file_path)
        
        response = (
            f"📈 <b>Финансовый анализ</b>\n\n"
            f"📅 Период: {analysis['period']['start']} - {analysis['period']['end']}\n"
            f"💰 Доходы: {analysis['total_income']:,.2f} ₽\n"
            f"💸 Расходы: {analysis['total_expenses']:,.2f} ₽\n\n"
            f"💡 <b>Рекомендации:</b>\n"
            f"{analysis['tax_optimization']}"
        )
        
        await message.answer(response)
    except Exception as e:
        await message.answer(f"❌ Ошибка анализа: {str(e)}")
    finally:
        await state.finish()
        if os.path.exists(file_path):
            os.remove(file_path)

async def on_shutdown(dp):
    """Корректное завершение работы"""
    await accountant.close()
    await bot.close()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_shutdown=on_shutdown)