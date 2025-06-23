import asyncio
import pandas as pd
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

API_TOKEN = '7999955718:AAFeqUDh6G3I63KHGcTN0mdEpvFR9hCsY5I'
CSV_PATH = 'df.csv'
OUTPUT_CSV = 'results.csv'

# Словарь для перевода названий столбцов
COLUMN_NAMES_RU = {
    'friends_opinion': 'Мнение друзей',
    'valuable_traits': 'Ценные качества',
    'shortcomings': 'Недостатки',
    'favorite_character': 'Любимый персонаж',
    'unpleasant_people': 'Неприятные люди'
}

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Загрузка данных анкет
def load_questionnaires():
    df = pd.read_csv(
        CSV_PATH,
        sep='\|',
        engine='python',
        quotechar='"',
        on_bad_lines='warn',
        header=None
    )
    df.columns = [
        'friends_opinion',
        'valuable_traits',
        'shortcomings',
        'favorite_character',
        'unpleasant_people'
    ]
    return df

questionnaires = load_questionnaires()

class Labeling(StatesGroup):
    waiting_for_label = State()

# Генератор всех необходимых сравнений
def comparison_generator(df):
    n = len(df)
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            # 1.2: 4-й из i, 1-й из j
            yield (i, j, 'favorite_character', 'friends_opinion')
            # 1.7: 4-й из i, 2-й из j
            yield (i, j, 'favorite_character', 'valuable_traits')
            # 1.7: 4-й из i, 3-й из j
            yield (i, j, 'favorite_character', 'shortcomings')
            # 1.8: 4-й из i, 5-й из j
            yield (i, j, 'favorite_character', 'unpleasant_people')
            # 1.9: 2-й из j, 1-й из i
            yield (j, i, 'valuable_traits', 'friends_opinion')
            # 1.9: 2-й из j, 2-й из i
            yield (j, i, 'valuable_traits', 'valuable_traits')
            # 1.10: 4-й из j, 1-й из i
            yield (j, i, 'favorite_character', 'friends_opinion')
            # 1.10: 4-й из j, 2-й из i
            yield (j, i, 'favorite_character', 'valuable_traits')
            # 1.10: 4-й из j, 3-й из i
            yield (j, i, 'favorite_character', 'shortcomings')
            # 1.10: 5-й из j, 1-й из i
            yield (j, i, 'unpleasant_people', 'friends_opinion')
            # 1.10: 5-й из j, 2-й из i
            yield (j, i, 'unpleasant_people', 'valuable_traits')
            # 1.10: 5-й из j, 3-й из i
            yield (j, i, 'unpleasant_people', 'shortcomings')

comparison_iter = comparison_generator(questionnaires)
results = []
current_comparison = None

@dp.message(Command('start'))
async def start_labeling(message: Message, state: FSMContext):
    global current_comparison
    await message.answer(
        "Добро пожаловать! Начнём оценку пар анкет.\n"
        "Для каждой пары оцените схожесть от 0 (совсем не похожи) до 1 (идентичны).\n"
        "Команды:\n"
        "/start - Начать или перезапустить оценку\n"
        "/save - Сохранить и загрузить текущие результаты\n"
        "/help - Показать справку"
    )
    await state.clear()
    await ask_next_comparison(message, state)

@dp.message(Command('help'))
async def help_menu(message: Message, state: FSMContext):
    await message.answer(
        "Справка:\n"
        "/start - Начать или перезапустить оценку\n"
        "/save - Сохранить и загрузить текущие результаты\n"
        "Просто введите число от 0 до 1 для оценки текущей пары."
    )

@dp.message(Command('save'))
async def save_and_upload(message: Message, state: FSMContext):
    if not results:
        await message.answer("Пока нет результатов для сохранения.")
        return
    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_CSV, index=False)
    await message.answer(f"Результаты сохранены в {OUTPUT_CSV}. Загружаю файл...")
    file = FSInputFile(OUTPUT_CSV)
    await message.answer_document(file, caption="Вот файл с результатами оценок.")

async def ask_next_comparison(message: Message, state: FSMContext):
    global current_comparison
    try:
        current_comparison = next(comparison_iter)
    except StopIteration:
        if results:
            df = pd.DataFrame(results)
            df.to_csv(OUTPUT_CSV, index=False)
            await message.answer(f"Готово! Результаты сохранены в {OUTPUT_CSV}. Используйте /save для загрузки файла.")
        else:
            await message.answer("Нет результатов для сохранения.")
        return
    i, j, col_i, col_j = current_comparison
    ans_1 = str(questionnaires.iloc[i][col_i])
    ans_2 = str(questionnaires.iloc[j][col_j])
    await message.answer(
        f"\nАнкета {i+1} ({COLUMN_NAMES_RU[col_i]}):\n{ans_1}\n\n"
        f"Анкета {j+1} ({COLUMN_NAMES_RU[col_j]}):\n{ans_2}\n\n"
        "Оцените схожесть (0-1):\n"
        "В любой момент можно ввести /save для сохранения результатов."
    )
    await state.set_state(Labeling.waiting_for_label)

@dp.message(Labeling.waiting_for_label)
async def process_label(message: Message, state: FSMContext):
    global results, current_comparison
    try:
        if message.text is None:
            raise ValueError
        score = float(message.text)
        if not 0 <= score <= 1:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите число от 0 до 1. Или введите /help для справки.")
        return
    if current_comparison is None:
        await message.answer("Нет активного сравнения. Используйте /start для начала.")
        return
    i, j, col_i, col_j = current_comparison
    ans_1 = str(questionnaires.iloc[i][col_i])
    ans_2 = str(questionnaires.iloc[j][col_j])
    results.append({'ans_1': ans_1, 'ans_2': ans_2, 'metka': score})
    await state.clear()
    await ask_next_comparison(message, state)

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())