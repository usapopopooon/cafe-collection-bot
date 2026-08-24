from cafe_collection.bot import CafeCollectionBot, create_bot


async def test_create_bot_uses_only_required_intents() -> None:
    bot = create_bot()
    try:
        assert isinstance(bot, CafeCollectionBot)
        assert bot.intents.guilds is True
        assert bot.intents.members is True
        assert bot.intents.message_content is False
    finally:
        await bot.close()
