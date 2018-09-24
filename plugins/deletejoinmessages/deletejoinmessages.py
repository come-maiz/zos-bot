from errbot import BotPlugin


class DeleteJoinMessages(BotPlugin):
    """
    Delete Telegram join messages.
    """

    _TELEGRAM_CHAT_ID_ZEPPELINOS = '-1001227311067'

    def callback_message(self, message):
        if (hasattr(message.to, 'id') and
                message.to.id == self._TELEGRAM_CHAT_ID_ZEPPELINOS):
            if message.body == '':
                if message.extras and message.extras['new_chat_members']:
                    self._bot.delete_message(message)
