from aiogram.filters import Command, CommandObject
from aiogram import Bot, Dispatcher, Router, F
from mistralai.models import UserMessage, AssistantMessage
from collections import defaultdict
from mistralai import Mistral
from aiogram.types import Message
from dataclasses import dataclass
from dotenv import load_dotenv
from typing import Dict, List
import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)

load_dotenv()

bot = Bot(token=os.getenv("BOT_TOKEN"))
client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
dp = Dispatcher()

router = Router()
dp.include_router(router)

user_messages: Dict[int, List[Dict[str, str]]] = defaultdict(list)


@dataclass
class AIResponse:
    role: str
    content: str
    tokens: int


async def process_ai_request(message: str, user_id: int) -> AIResponse:
    chat_messages = []
    for msg in user_messages[user_id][-10:]:
        if msg["role"] == "user":
            chat_messages.append(UserMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            chat_messages.append(AssistantMessage(content=msg["content"]))

    chat_messages.append(UserMessage(content=message))

    chat_response = await client.chat.complete_async(
        model="mistral-large-latest", messages=chat_messages
    )

    return AIResponse(
        role=chat_response.choices[0].message.role,
        content=chat_response.choices[0].message.content,
        tokens=chat_response.usage.total_tokens,
    )


@router.message(Command("clear"))
async def clear_history(message: Message):
    user_id = message.from_user.id
    if user_id in user_messages:
        user_messages[user_id].clear()
        await message.reply("История сообщений очищена.", parse_mode="Markdown")
    else:
        await message.reply(
            "У вас уже очищена история сообщений.", parse_mode="Markdown"
        )


@router.message(Command("history"))
async def show_history(message: Message):
    user_id = message.from_user.id
    if not user_messages[user_id]:
        await message.reply("История сообщений пуста.")
        return

    history_text = "История сообщений:\n\n"
    for msg in user_messages[user_id]:
        role = "Вы" if msg["role"] == "user" else "Ассистент"
        history_text += f"{role}: {msg['content'][:100]}...\n\n"

    await message.reply(history_text, parse_mode="Markdown")


@router.message(Command("prompt"))
async def handle_prompt_command(message: Message, command: CommandObject):
    if not command.args:
        await message.reply("Пожалуйста, введите ваше сообщение.")
        return

    user_id = message.from_user.id
    ai_response = await process_ai_request(command.args, user_id)

    user_messages[user_id].append({"role": "user", "content": command.args})
    user_messages[user_id].append({"role": "assistant", "content": ai_response.content})

    await message.reply(ai_response.content, parse_mode="Markdown")


@router.message(F.chat.type == "private")
async def handle_private_message(message: Message):
    user_id = message.from_user.id

    ai_response = await process_ai_request(message.text, user_id)

    user_messages[user_id].append({"role": "user", "content": message.text})
    user_messages[user_id].append({"role": "assistant", "content": ai_response.content})

    await message.reply(ai_response.content, parse_mode="Markdown")


@router.message()
async def handle_other_messages(message: Message):
    pass


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
