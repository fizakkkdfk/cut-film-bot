import os
import subprocess
from threading import Thread
import telebot
from flask import Flask
import yt_dlp
from telebot import types

TOKEN = '8859717636:AAE-sz8fM74GLEprYv_MWTWEOb0p0ZdDM54'
bot = telebot.TeleBot(TOKEN)

user_data = {}

# Создаем простой веб-сервер, чтобы Render видел открытый порт
app = Flask('')


@app.route('/')
def home():
  return 'Bot is alive!'


def run_web():
  app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))


@bot.message_handler(commands=['start'])
def send_welcome(message):
  # Создаем постоянное меню из кнопок под чатом
  markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
  btn_help = types.KeyboardButton('ℹ️ Помощь')
  btn_about = types.KeyboardButton('📁 О боте')
  btn_clear = types.KeyboardButton('🧹 Очистить память')
  markup.add(btn_help, btn_about)
  markup.add(btn_clear)

  bot.reply_to(
      message,
      'Привет! 👋 Отправь мне ссылку на видео (YouTube, VK или Рутуб). Я скачаю'
      ' его, обрежу в 9:16, наложу твой баннер и нарежу на кусочки. Пришлю'
      ' превью, чтобы ты выбрал, что скачать!',
      reply_markup=markup,
  )


# Обработка нажатий на кнопки нижнего меню
@bot.message_handler(
    func=lambda message: message.text
    in ['ℹ️ Помощь', '📁 О боте', '🧹 Очистить память']
)
def handle_menu_buttons(message):
  if message.text == 'ℹ️ Помощь':
    bot.reply_to(
        message,
        '📖 **Как пользоваться ботом:**\n1. Просто отправьте ссылку на видео'
        ' (YouTube, VK Видео, RuTube).\n2. Бот обработает его и пришлет'
        ' нарезку кусочков по 60 секунд с превью.\n3. Нажимайте кнопку под'
        ' нужным куском, чтобы скачать его!',
        parse_mode='Markdown',
    )
  elif message.text == '📁 О боте':
    bot.reply_to(
        message,
        '🤖 Этот бот создан для автоматической нарезки длинных видео в формат'
        ' Shorts/Reels/TikTok (9:16) с кастомным баннером.',
    )
  elif message.text == '🧹 Очистить память':
    clean_garbage()
    bot.reply_to(message, '🧹 Временные файлы на сервере успешно очищены!')


@bot.message_handler(func=lambda message: True)
def process_video(message):
  url = message.text
  chat_id = message.chat.id
  msg = bot.reply_to(message, '⏳ Скачиваю видео...')

  input_file = 'input.mp4'
  output_pattern = 'part_%03d.mp4'
  banner_file = 'banner.png'

  ydl_opts = {
      'format': 'best[ext=mp4]',
      'outtmpl': input_file,
      'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
      'socket_timeout': 30,
  }

  try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      info = ydl.extract_info(url, download=True)
      video_title = info.get('title', 'Интересный момент из фильма')

    bot.edit_message_text(
        '✂️ Нарезаю, кадрирую и накладываю баннер...',
        chat_id,
        msg.message_id,
    )

    if os.path.exists(banner_file):
      filter_complex = (
          '[0:v]crop=ih*(9/16):ih[v_crop];'
          '[v_crop][1:v]overlay=(W-w)/2:H-h-30[v_final]'
      )
      command = [
          'ffmpeg',
          '-i',
          input_file,
          '-i',
          banner_file,
          '-filter_complex',
          filter_complex,
          '-map',
          '[v_final]',
          '-map',
          '0:a',
          '-c:v',
          'libx264',
          '-c:a',
          'aac',
          '-f',
          'segment',
          '-segment_time',
          '60',
          '-reset_timestamps',
          '1',
          output_pattern,
      ]
    else:
      command = [
          'ffmpeg',
          '-i',
          input_file,
          '-vf',
          'crop=ih*(9/16):ih',
          '-c:v',
          'libx264',
          '-c:a',
          'aac',
          '-f',
          'segment',
          '-segment_time',
          '60',
          '-reset_timestamps',
          '1',
          output_pattern,
      ]

    subprocess.run(command, check=True)
    if os.path.exists(input_file):
      os.remove(input_file)

    parts = sorted([f for f in os.listdir('.') if f.startswith('part_')])
    if not parts:
      bot.send_message(chat_id, '❌ Ошибка: не удалось нарезать видео.')
      return

    user_data[chat_id] = {'parts': parts, 'title': video_title}

    bot.edit_message_text(
        f'✅ Готово! Нарезано частей: {len(parts)}. Создаю превью...',
        chat_id,
        msg.message_id,
    )

    for i, part in enumerate(parts):
      thumb_file = f'thumb_{i}.jpg'
      subprocess.run([
          'ffmpeg',
          '-ss',
          '00:00:01',
          '-i',
          part,
          '-vframes',
          '1',
          thumb_file,
      ])

      markup = types.InlineKeyboardMarkup()
      btn_get = types.InlineKeyboardButton(
          f'📥 Скачать часть {i+1}', callback_data=f'get_part_{i}'
      )
      markup.add(btn_get)

      if os.path.exists(thumb_file):
        with open(thumb_file, 'rb') as th:
          bot.send_photo(
              chat_id,
              th,
              caption=(
                  f'🎞 **Кусок №{i+1}**\nНажми кнопку ниже, чтобы получить этот'
                  ' файл.'
              ),
              reply_markup=markup,
              parse_mode='Markdown',
          )
        os.remove(thumb_file)
      else:
        bot.send_message(chat_id, f'Кусок №{i+1}', reply_markup=markup)

    tags = (
        f'🎬 **Готовое описание для поста:**\n\n{video_title}\n\n#фильмы'
        ' #моменты #рекомендации #кино #shorts #tiktok'
    )
    bot.send_message(chat_id, tags, parse_mode='Markdown')

  except Exception as e:
    bot.send_message(chat_id, f'❌ Произошла ошибка: {e}')
    clean_garbage()


@bot.callback_query_handler(func=lambda call: call.data.startswith('get_part_'))
def send_selected_part(call):
  chat_id = call.message.chat.id
  part_index = int(call.data.split('_')[2])

  if chat_id in user_data and 'parts' in user_data[chat_id]:
    parts = user_data[chat_id]['parts']
    if part_index < len(parts):
      part_file = parts[part_index]
      if os.path.exists(part_file):
        bot.answer_callback_query(call.id, 'Отправляю видео...')
        with open(part_file, 'rb') as f:
          bot.send_video(chat_id, f, caption=f'Ваш ролик (Часть {part_index+1})')
        return

  bot.answer_callback_query(
      call.id, '❌ Файл устарел или уже удален. Отправьте ссылку заново.'
  )


def clean_garbage():
  for f in os.listdir('.'):
    if (
        f.startswith('part_')
        or f == 'input.mp4'
        or f.startswith('thumb_' or f == 'banner.png')
    ):
      try:
        os.remove(f)
      except:
        pass


if __name__ == '__main__':
  t = Thread(target=run_web)
  t.start()
  bot.infinity_polling()
  
