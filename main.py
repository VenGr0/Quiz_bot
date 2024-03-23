import asyncio
import logging
from aiogram import Bot, Dispatcher
from handlers import router

API_TOKEN = '7183695295:AAEw-gDIC-BucWTDnDCkHTF3gNKtBWP7IM0'
# Объект бота
bot = Bot(token=API_TOKEN)
# Диспетчер
dp = Dispatcher()


async def main():
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Exit')
