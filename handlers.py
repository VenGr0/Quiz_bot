from aiogram.filters.command import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram import F, Router, types
from quiz_questions import quiz_data
import aiosqlite

router = Router()

# Зададим имя базы данных
DB_NAME = 'quiz_bot.db'


# Функция для генерации клавиатуры с вариантами ответов
def generate_options_keyboard(answer_options, right_answer):
    # Создаем объект InlineKeyboardBuilder для построения клавиатуры
    builder = InlineKeyboardBuilder()

    # Перебираем все варианты ответов
    for option in answer_options:
        # Создаем кнопку для каждого варианта ответа
        builder.add(types.InlineKeyboardButton(
            # Устанавливаем текст кнопки равным варианту ответа
            text=option,
            # Устанавливаем callback_data в зависимости от того, является ли вариант ответа правильным
            callback_data="right_answer" if option == right_answer else "wrong_answer")
        )

    # Выравниваем кнопки по одной в ряд
    builder.adjust(1)

    # Возвращаем сгенерированную клавиатуру
    return builder.as_markup()


# Хэндлер для обработки нажатия на кнопку с правильным ответом
@router.callback_query(F.data == "right_answer")
async def right_answer(callback: types.CallbackQuery):
    # Удаляем клавиатуру с вариантами ответов
    await callback.bot.edit_message_reply_markup(
        chat_id=callback.from_user.id,  # Идентификатор чата
        message_id=callback.message.message_id,  # Идентификатор сообщения
        reply_markup=None  # Удаляем клавиатуру
    )
    await update_quiz_result(callback.from_user.id, True)  # создание таблицы счета

    # Отправляем сообщение с подтверждением правильного ответа
    await callback.message.answer("Верно!")

    # Получаем индекс текущего вопроса из базы данных
    current_question_index = await get_quiz_index(callback.from_user.id)

    # Обновляем номер текущего вопроса в базе данных
    current_question_index += 1
    await update_quiz_index(callback.from_user.id, current_question_index)

    # Если текущий вопрос не последний, задаем следующий вопрос
    if current_question_index < len(quiz_data):
        await get_question(callback.message, callback.from_user.id)
    else:
        # Если текущий вопрос последний, сообщаем об окончании квиза
        await callback.message.answer("Это был последний вопрос. Квиз завершен!")
        correct_answers, total_questions = await update_quiz_result(callback.from_user.id, True)
        await callback.message.answer(
            f"Вы ответили на {correct_answers - 1} вопросов из {total_questions - 1} правильно.")
        await update_quiz_result(callback.from_user.id, reset=True)  # Обнуляем статистику


# Хэндлер для обработки нажатия на кнопку с неправильным ответом
@router.callback_query(F.data == "wrong_answer")
async def wrong_answer(callback: types.CallbackQuery):
    # Удаляем клавиатуру с вариантами ответов
    await callback.bot.edit_message_reply_markup(
        chat_id=callback.from_user.id,  # Идентификатор чата
        message_id=callback.message.message_id,  # Идентификатор сообщения
        reply_markup=None  # Удаляем клавиатуру
    )
    await update_quiz_result(callback.from_user.id, False)
    # Получаем индекс текущего вопроса из базы данных
    current_question_index = await get_quiz_index(callback.from_user.id)
    # Определяем правильный ответ
    correct_option = quiz_data[current_question_index]['correct_option']

    # Отправляем сообщение с указанием правильного ответа
    await callback.message.answer(
        f"Неправильно. Правильный ответ: {quiz_data[current_question_index]['options'][correct_option]}")

    # Обновляем номер текущего вопроса в базе данных
    current_question_index += 1
    await update_quiz_index(callback.from_user.id, current_question_index)

    # Если текущий вопрос не последний, задаем следующий вопрос
    if current_question_index < len(quiz_data):
        await get_question(callback.message, callback.from_user.id)
    else:
        # Если текущий вопрос последний, сообщаем об окончании квиза
        await callback.message.answer("Это был последний вопрос. Квиз завершен!")
        correct_answers, total_questions = await update_quiz_result(callback.from_user.id, False)
        await callback.message.answer(
            f"Вы ответили на {correct_answers - 1} вопросов из {total_questions - 1} правильно.")
        await update_quiz_result(callback.from_user.id, reset=True)  # Обнуляем статистику


async def update_quiz_result(user_id, is_correct=True, reset=False):
    if reset:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute('UPDATE quiz_results SET correct_answers = 0, total_questions = 0 WHERE user_id = (?)',
                             (user_id,))
            await db.commit()
        return 0, 0

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT correct_answers, total_questions FROM quiz_results WHERE user_id = (?)',
                              (user_id,)) as cursor:
            results = await cursor.fetchone()
            if results is not None:
                correct_answers, total_questions = results
            else:
                correct_answers, total_questions = 0, 0

    if is_correct:
        correct_answers += 1
    total_questions += 1

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            'INSERT OR REPLACE INTO quiz_results (user_id, correct_answers, total_questions) VALUES (?, ?, ?)',
            (user_id, correct_answers, total_questions))
        await db.commit()

    return correct_answers, total_questions


# Хэндлер на команду /start
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    # Создаем клавиатуру с кнопкой "Начать игру"
    builder = ReplyKeyboardBuilder()
    builder.add(types.KeyboardButton(text="Начать игру"))

    # Приветствуем пользователя и отправляем сообщение с клавиатурой
    await message.answer("Добро пожаловать в квиз!", reply_markup=builder.as_markup(resize_keyboard=True))


# Хэндлер на /stats
@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    user_id = message.from_user.id

    # Получение статистики квиза из бд
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute('SELECT correct_answers, total_questions FROM quiz_results WHERE user_id = (?)',
                              (user_id,)) as cursor:
            results = await cursor.fetchone()
            if results is not None:
                correct_answers, total_questions = results
                percentage = round(correct_answers / total_questions * 100, 2)
                await message.answer(
                    f"Ваша статистика:\nПравильных ответов: {correct_answers}\nВсего вопросов: {total_questions}\nПроцент правильных ответов: {percentage}%")
            else:
                await message.answer("Вы еще не проходили квиз")


# Функция для получения текущего вопроса
async def get_question(message, user_id):
    # Получаем индекс текущего вопроса из базы данных
    current_question_index = await get_quiz_index(user_id)

    # Определяем правильный ответ
    correct_index = quiz_data[current_question_index]['correct_option']

    # Получаем варианты ответов
    opts = quiz_data[current_question_index]['options']

    # Генерируем клавиатуру с вариантами ответов
    kb = generate_options_keyboard(opts, opts[correct_index])

    # Отправляем текущий вопрос с клавиатурой
    await message.answer(f"{quiz_data[current_question_index]['question']}", reply_markup=kb)


# Функция для старта нового квиза
async def new_quiz(message):
    # Получаем идентификатор пользователя
    user_id = message.from_user.id

    # Обнуляем номер текущего вопроса в базе данных
    current_question_index = 0
    await update_quiz_index(user_id, current_question_index)

    # Задаем первый вопрос
    await get_question(message, user_id)


async def get_quiz_index(user_id):
    # Подключаемся к базе данных
    async with aiosqlite.connect(DB_NAME) as db:
        # Получаем запись для заданного пользователя
        async with db.execute('SELECT question_index FROM quiz_state WHERE user_id = (?)', (user_id,)) as cursor:
            # Возвращаем результат
            results = await cursor.fetchone()
            if results is not None:
                return results[0]
            else:
                return 0


async def update_quiz_index(user_id, index):
    # Создаем соединение с базой данных (если она не существует, она будет создана)
    async with aiosqlite.connect(DB_NAME) as db:
        # Вставляем новую запись или заменяем ее, если с данным user_id уже существует
        await db.execute('INSERT OR REPLACE INTO quiz_state (user_id, question_index) VALUES (?, ?)', (user_id, index))
        # Сохраняем изменения
        await db.commit()


# Хэндлер на команду /quiz
@router.message(F.text == "Начать игру")
@router.message(Command("quiz"))
async def cmd_quiz(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        # Создаем таблицу для результатов
        await db.execute(
            '''CREATE TABLE IF NOT EXISTS quiz_results (correct_answers INTEGER,
    total_questions INTEGER,
    user_id         INTEGER PRIMARY KEY
                            NOT NULL)''')
    await message.answer(f"Давайте начнем квиз!")
    await new_quiz(message)


async def create_table():
    # Создаем соединение с базой данных (если она не существует, она будет создана)
    async with aiosqlite.connect(DB_NAME) as db:
        # Создаем таблицу
        await db.execute(
            '''CREATE TABLE IF NOT EXISTS quiz_state (user_id INTEGER PRIMARY KEY, question_index INTEGER)''')
        # Сохраняем изменения
        await db.commit()


# Запуск процесса поллинга новых апдейтов
async def main():
    # Запускаем создание таблицы базы данных
    await create_table()
