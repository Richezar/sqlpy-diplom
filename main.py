import configparser
import random
import sqlalchemy

from sqlalchemy.orm import sessionmaker
from telebot import types, TeleBot, custom_filters
from telebot.storage import StateMemoryStorage
from telebot.handler_backends import State, StatesGroup
from db.models import create_tables, insert_word_db, Word, UserWord, User


print('Start telegram bot...')

state_storage = StateMemoryStorage()
config = configparser.ConfigParser()
config.read('token.ini')
bot = TeleBot(config['TG']['token'], state_storage=state_storage)

known_users = []
userStep = {}
buttons = []

engine = sqlalchemy.create_engine('postgresql://')
Session = sessionmaker(bind=engine)
session = Session()
create_tables(engine)
insert_word_db(session)

def show_hint(*lines):
    return '\n'.join(lines)

def show_target(data):
    return f"{data['target_word']} -> {data['translate_word']}"

def user_word(engine, cid):
    session = (sessionmaker(bind=engine))()
    all_word = session.query(Word.word).all()
    user_words = session.query(UserWord.word).join(User, User.id == UserWord.id_user).filter(User.cid == cid).all()
    words = len(all_word) + len(user_words)
    session.close()
    return words

def add_users(engine, cid):
    session = (sessionmaker(bind=engine))()
    session.add(User(cid=cid))
    session.commit()
    session.close()

def add_words(engine, cid, word, translate):
    session = (sessionmaker(bind=engine))()
    id_user = session.query(User.id).filter(User.cid == cid).first()[0]
    session.add(UserWord(word=word, translate=translate, id_user=id_user))
    session.commit()
    session.close()

def delete_word(engine, cid, word):
    session = (sessionmaker(bind=engine))()
    id_user = session.query(User.id).filter(User.cid == cid).first()[0]
    session.query(UserWord).filter(UserWord.id_user == id_user, UserWord.word == word).delete()
    session.commit()
    session.close()

def random_word(engine, user_id):
    session = (sessionmaker(bind=engine))()
    words = session.query(UserWord.word, UserWord.translate) \
        .join(User, User.id == UserWord.id_user) \
        .filter(User.cid == user_id).all()
    all_words = session.query(Word.word, Word.translation).all()
    result = all_words + words
    result = random.sample(result, 4)
    session.close()
    return result

class Command:
    ADD_WORD = 'Добавить слово ➕'
    DELETE_WORD = 'Удалить слово🔙'
    NEXT = 'Дальше ⏭'

class MyStates(StatesGroup):
    target_word = State()
    translate_word = State()
    another_words = State()

welcome_text = """Привет 👋 Давай попрактикуемся в английском языке. Тренировки можешь проходить в удобном для себя темпе.\nУ тебя есть возможность использовать тренажёр, как конструктор, и собирать свою собственную базу для обучения. Для этого воспрользуйся инструментами:\nдобавить слово ➕,\nудалить слово 🔙.\nНу что, начнём ⬇️"""

@bot.message_handler(commands=['cards', 'start'])
def create_cards(message):
    cid = message.chat.id
    if cid not in known_users:
        known_users.append(cid)
        add_users(engine, cid)
        userStep[cid] = 0
        bot.send_message(cid, welcome_text)
    markup = types.ReplyKeyboardMarkup(row_width=2)

    global buttons
    buttons = []
    tmp = random_word(engine, cid)
    target_word = tmp[0][0] # брать из БД
    translate = tmp[0][1]  # брать из БД
    target_word_btn = types.KeyboardButton(target_word)
    buttons.append(target_word_btn)
    others = [word[0] for word in tmp[1:]]  # брать из БД

    other_words_btns = [types.KeyboardButton(word) for word in others]
    buttons.extend(other_words_btns)
    random.shuffle(buttons)
    next_btn = types.KeyboardButton(Command.NEXT)
    add_word_btn = types.KeyboardButton(Command.ADD_WORD)
    delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
    buttons.extend([next_btn, add_word_btn, delete_word_btn])

    markup.add(*buttons)

    greeting = f"Выбери перевод слова:\n🇷🇺 {translate}"
    bot.send_message(message.chat.id, greeting, reply_markup=markup)
    bot.set_state(message.from_user.id, MyStates.target_word, message.chat.id)
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data['target_word'] = target_word
        data['translate_word'] = translate
        data['other_words'] = others


@bot.message_handler(func=lambda message: message.text == Command.NEXT)
def next_cards(message):
    create_cards(message)


@bot.message_handler(func=lambda message: message.text == Command.DELETE_WORD)
def delete_word(message):
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        delete_word(engine, message.chat.id, data['target_word'])
        bot.send_message(message.chat.id, 'Слово удалено')


@bot.message_handler(func=lambda message: message.text == Command.ADD_WORD)
def add_word(message):
    cid = message.chat.id
    userStep[cid] = 1
    bot.send_message(cid, "Введите слово на английском")
    bot.set_state(message.from_user.id, MyStates.target_word, message.chat.id)


@bot.message_handler(func=lambda message: True, content_types=['text'])
def message_reply(message):
    text = message.text
    markup = types.ReplyKeyboardMarkup(row_width=2)
    cid = message.chat.id
    if userStep[cid] == 0:
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            target_word = data['target_word']
            if text == target_word:
                hint = show_target(data)
                hint_text = ["Отлично!❤", hint]
                next_btn = types.KeyboardButton(Command.NEXT)
                add_word_btn = types.KeyboardButton(Command.ADD_WORD)
                delete_word_btn = types.KeyboardButton(Command.DELETE_WORD)
                buttons.extend([next_btn, add_word_btn, delete_word_btn])
                hint = show_hint(*hint_text)
            else:
                for btn in buttons:
                    if btn.text == text:
                        btn.text = text + '❌'
                        break
                hint = show_hint("Допущена ошибка!",
                                 f"Попробуй ещё раз вспомнить слово 🇷🇺{data['translate_word']}")
        bot.send_message(message.chat.id, hint, reply_markup=markup)
    elif userStep[cid] == 1:
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['target_word'] = text
            bot.send_message(cid, "Введите перевод слова на русском")
            bot.set_state(message.from_user.id, MyStates.translate_word, message.chat.id)
            userStep[cid] = 2
    elif userStep[cid] == 2:
        with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
            data['translate_word'] = text
            add_words(engine, cid, data['target_word'], data['translate_word'])
            bot.send_message(cid, 'Слово добавлено')
            userStep[cid] = 0
            bot.send_message(cid, f'Вы изучаете {user_word(engine, cid)} слов')





bot.add_custom_filter(custom_filters.StateFilter(bot))

bot.infinity_polling(skip_pending=True)