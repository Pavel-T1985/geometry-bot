import os
from vkbottle.bot import Bot, Message
from vkbottle.tools import Keyboard, Text
from gigachat import GigaChat

# ─── Конфигурация ───────────────────────────────────────────────
VK_TOKEN = os.environ.get("VK_TOKEN", "")
GIGACHAT_KEY = os.environ.get("GIGACHAT_KEY", "")
GIGACHAT_SCOPE = "GIGACHAT_API_PERS"

# ─── Системный промпт ───────────────────────────────────────────
SYSTEM_PROMPT = """Ты — дружелюбный репетитор по геометрии для учеников 7-11 классов.
Программа — по учебнику Атанасяна. Поддержка ОГЭ и ЕГЭ.

ПРАВИЛА:
1. Всегда давай ПОЛНОЕ пошаговое решение с объяснениями.
2. Если ученик указал класс — используй только материал, пройденный до этого класса.
   (7 класс: базовые треугольники, окружность; 8 класс: четырёхугольники, площади,
    теорема Пифагора; 9 класс: векторы, метод координат, подобие;
    10-11: стереометрия, метод координат в пространстве.)
3. Если класс не указан — решай в общем виде, но предупреди, если используешь
   материал старших классов.
4. После решения пиши краткую идею (1-2 предложения): на какую теорему или свойство
   опирается задача.
5. Объясняй простым языком, как старший товарищ. Без канцелярита.
6. При объяснении темы — структурируй: определение, затем свойства, затем пример.
7. Для задач ОГЭ/ЕГЭ — давай реальные формулировки из банка ФИПИ.
8. Формулы пиши простым текстом (например: S = (a*h)/2), без LaTeX.
9. Если нужно построение — опиши чертёж словами.
10. Отвечай только на русском языке."""

# ─── Клавиатуры ────────────────────────────────────────────────
def main_keyboard():
    kb = Keyboard(one_time=False)
    kb.add(Text("📐 Решить задачу", payload={"action": "solve"}))
    kb.add(Text("📚 Объяснить тему", payload={"action": "topic"}))
    kb.row()
    kb.add(Text("📝 Задание ОГЭ", payload={"action": "oge"}))
    kb.add(Text("🎓 Задание ЕГЭ", payload={"action": "ege"}))
    kb.row()
    kb.add(Text("❓ Помощь", payload={"action": "help"}))
    return kb.get_json()

def cancel_keyboard():
    kb = Keyboard(one_time=True)
    kb.add(Text("⬅️ Назад", payload={"action": "menu"}))
    return kb.get_json()

# ─── Состояния пользователей ───────────────────────────────────
user_states = {}

bot = Bot(token=VK_TOKEN)

# ─── Запрос к GigaChat с обработкой ошибок ─────────────────────
async def ask_gigachat(user_message, system_prompt=SYSTEM_PROMPT):
    try:
        async with GigaChat(
            credentials=GIGACHAT_KEY,
            scope=GIGACHAT_SCOPE,
            verify_ssl_certs=False,
        ) as client:
            payload = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
            }
            response = await client.achat(payload)
            try:
                return response.choices[0].message.content
            except (AttributeError, IndexError, TypeError):
                try:
                    return response.messages[0].content[0].text
                except (AttributeError, IndexError, TypeError):
                    return str(response)
    except Exception as e:
        error_text = str(e)

        # 402 — исчерпан лимит токенов
        if "402" in error_text or "Payment Required" in error_text:
            return ("😔 Сегодня лимит запросов исчерпан.\n"
                    "Попробуй завтра — лимит обновится.\n\n"
                    "Если это сообщение появляется часто — "
                    "напиши администратору группы.")

        # 429 — слишком много запросов в минуту
        if "429" in error_text or "Too Many Requests" in error_text:
            return ("⏳ Слишком много запросов подряд.\n"
                    "Подожди минутку и попробуй ещё раз.")

        # 401/403 — проблема с ключом
        if "401" in error_text or "403" in error_text:
            return ("⚠️ Техническая проблема на стороне бота.\n"
                    "Администратор уже уведомлён.")

        # Прочие ошибки
        return ("⚠️ Не удалось обработать запрос.\n"
                "Попробуй переформулировать или повторить позже.")

# ─── Отправка длинных сообщений ────────────────────────────────
async def send_long(message, text, keyboard=None):
    for i in range(0, len(text), 4000):
        chunk = text[i:i+4000]
        if i + 4000 >= len(text) and keyboard:
            await message.answer(chunk, keyboard=keyboard)
        else:
            await message.answer(chunk)

# ─── Команда "Начать" ─────────────────────────────────────────
@bot.on.message(text=["Начать", "Start", "start", "/start",
                       "привет", "Привет"])
async def start_handler(message: Message):
    user_states[message.from_id] = None
    await message.answer(
        "Привет! Я бот-репетитор по геометрии 📐\n\n"
        "Помогаю с задачами, объясняю темы и готовлю к ОГЭ/ЕГЭ.\n\n"
        "Выбери, что нужно:",
        keyboard=main_keyboard(),
    )

# ─── Кнопки меню ──────────────────────────────────────────────
@bot.on.message(payload_map={"action": "menu"})
async def menu_handler(message: Message):
    user_states[message.from_id] = None
    await message.answer("Главное меню 👇", keyboard=main_keyboard())

@bot.on.message(payload_map={"action": "solve"})
async def solve_handler(message: Message):
    user_states[message.from_id] = "solve"
    await message.answer(
        "Напиши условие задачи текстом.\n"
        "Если знаешь класс — напиши в начале: «8 класс. В треуг. ABC...»\n\n"
        "Я дам полное пошаговое решение с объяснениями.",
        keyboard=cancel_keyboard(),
    )

@bot.on.message(payload_map={"action": "topic"})
async def topic_handler(message: Message):
    user_states[message.from_id] = "topic"
    await message.answer(
        "Напиши название темы.\n"
        "Например: «признаки равенства треугольников», "
        "«теорема Пифагора».\n\nЯ объясню простым языком.",
        keyboard=cancel_keyboard(),
    )

@bot.on.message(payload_map={"action": "oge"})
async def oge_handler(message: Message):
    await message.answer("Генерирую задачу ОГЭ... ⏳",
                         keyboard=cancel_keyboard())
    prompt = ("Дай одну реальную задачу из банка ФИПИ для ОГЭ по "
              "геометрии. Только условие, без решения.")
    response = await ask_gigachat(prompt)
    await send_long(message, response +
                    "\n\nРеши и пришли мне — проверю!")
    user_states[message.from_id] = "oge_check"

@bot.on.message(payload_map={"action": "ege"})
async def ege_handler(message: Message):
    await message.answer("Генерирую задачу ЕГЭ... ⏳",
                         keyboard=cancel_keyboard())
    prompt = ("Дай одну реальную задачу из банка ФИПИ для ЕГЭ по "
              "математике (планиметрия или стереометрия). Только "
              "условие, без решения.")
    response = await ask_gigachat(prompt)
    await send_long(message, response +
                    "\n\nРеши и пришли мне — проверю!")
    user_states[message.from_id] = "ege_check"

@bot.on.message(payload_map={"action": "help"})
async def help_handler(message: Message):
    await message.answer(
        "❓ Как пользоваться:\n\n"
        "📐 Решить задачу — напиши условие, получишь решение.\n"
        "📚 Объяснить тему — напиши тему, получишь объяснение.\n"
        "📝 ОГЭ — бот даст задачу, ты решишь, бот проверит.\n"
        "🎓 ЕГЭ — то же для ЕГЭ.\n\n"
        "Совет: указывай класс, чтобы решение соответствовало "
        "программе.",
        keyboard=main_keyboard(),
    )

# ─── Текстовые сообщения по режиму ─────────────────────────────
@bot.on.message()
async def text_handler(message: Message):
    text = message.text.strip()
    if not text:
        return

    uid = message.from_id
    state = user_states.get(uid)

    if state is None:
        await message.answer("Выбери действие 👇",
                             keyboard=main_keyboard())
        return

    if state == "solve":
        await message.answer("Решаю... ⏳",
                             keyboard=cancel_keyboard())
        prompt = ("Реши задачу по геометрии пошагово с "
                  "объяснениями:\n\n" + text)
        response = await ask_gigachat(prompt)
        await send_long(message, response,
                        keyboard=main_keyboard())
        user_states[uid] = None
        return

    if state == "topic":
        await message.answer("Объясняю... ⏳",
                             keyboard=cancel_keyboard())
        prompt = ("Объясни тему по геометрии простым языком с "
                  "примером: определение, свойства, пример.\n\n"
                  "Тема: " + text)
        response = await ask_gigachat(prompt)
        await send_long(message, response,
                        keyboard=main_keyboard())
        user_states[uid] = None
        return

    if state == "oge_check":
        await message.answer("Проверяю... ⏳",
                             keyboard=cancel_keyboard())
        prompt = ("Ученик решил задачу ОГЭ по геометрии. Проверь. "
                  "Если ошибка — объясни. Если верно — "
                  "похвали.\n\nРешение:\n" + text)
        response = await ask_gigachat(prompt)
        await send_long(message, response,
                        keyboard=main_keyboard())
        user_states[uid] = None
        return

    if state == "ege_check":
        await message.answer("Проверяю... ⏳",
                             keyboard=cancel_keyboard())
        prompt = ("Ученик решил задачу ЕГЭ по математике "
                  "(геометрия). Проверь. Если ошибка — объясни. "
                  "Если верно — похвали.\n\nРешение:\n" + text)
        response = await ask_gigachat(prompt)
        await send_long(message, response,
                        keyboard=main_keyboard())
        user_states[uid] = None
        return

    user_states[uid] = None
    await message.answer("Выбери действие 👇",
                         keyboard=main_keyboard())

# ─── Запуск ───────────────────────────────────────────────────
if __name__ == "__main__":
    print("Бот запущен! Ожидание сообщений...")
    bot.run_forever()