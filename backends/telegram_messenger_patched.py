import logging
import sys

from errbot.backends.base import RoomError, Identifier, Person, RoomOccupant, Stream, ONLINE, Room
from errbot.backends.telegram_messenger import TelegramBotFilter, TelegramPerson, TelegramMUCOccupant, TelegramRoom
from errbot.core import ErrBot
from errbot.rendering import text
from errbot.rendering.ansiext import enable_format, TEXT_CHRS


# Can't use __name__ because of Yapsy
log = logging.getLogger('errbot.backends.telegrampatched')

TELEGRAM_MESSAGE_SIZE_LIMIT = 1024
UPDATES_OFFSET_KEY = '_telegram_updates_offset'

try:
    import telegram
except ImportError:
    log.exception("Could not start the Telegram back-end")
    log.fatal(
        "You need to install the telegram support in order "
        "to use the Telegram backend.\n"
        "You should be able to install this package using:\n"
        "pip install errbot[telegram]"
    )
    sys.exit(1)


class TelegramPatchedBackend(ErrBot):
    def __init__(self, config):
        super().__init__(config)
        config.MESSAGE_SIZE_LIMIT = TELEGRAM_MESSAGE_SIZE_LIMIT
        logging.getLogger('telegram.bot').addFilter(TelegramBotFilter())

        identity = config.BOT_IDENTITY
        self.token = identity.get('token', None)
        if not self.token:
            log.fatal(
                "You need to supply a token for me to use. You can obtain "
                "a token by registering your bot with the Bot Father (@BotFather)"
            )
            sys.exit(1)
        self.telegram = None  # Will be initialized in serve_once
        self.bot_instance = None  # Will be set in serve_once

        compact = config.COMPACT_OUTPUT if hasattr(config, 'COMPACT_OUTPUT') else False
        enable_format('text', TEXT_CHRS, borders=not compact)
        self.md_converter = text()

    def serve_once(self):
        log.info("Initializing connection")
        try:
            self.telegram = telegram.Bot(token=self.token)
            me = self.telegram.getMe()
        except telegram.TelegramError as e:
            log.error("Connection failure: %s", e.message)
            return False

        self.bot_identifier = TelegramPerson(
            id=me.id,
            first_name=me.first_name,
            last_name=me.last_name,
            username=me.username
        )

        log.info("Connected")
        self.reset_reconnection_count()
        self.connect_callback()

        try:
            offset = self[UPDATES_OFFSET_KEY]
        except KeyError:
            offset = 0

        try:
            while True:
                log.debug("Getting updates with offset %s", offset)
                for update in self.telegram.getUpdates(offset=offset, timeout=60):
                    offset = update.update_id + 1
                    self[UPDATES_OFFSET_KEY] = offset
                    log.debug("Processing update: %s", update)
                    if not hasattr(update, 'message'):
                        log.warning("Unknown update type (no message present)")
                        continue
                    try:
                        self._handle_message(update.message)
                    except Exception:
                        log.exception("An exception occurred while processing update")
                log.debug("All updates processed, new offset is %s", offset)
        except KeyboardInterrupt:
            log.info("Interrupt received, shutting down..")
            return True
        except Exception:
            log.exception("Error reading from Telegram updates stream:")
        finally:
            log.debug("Triggering disconnect callback")
            self.disconnect_callback()

    def _handle_message(self, message):
        """
        Handle a received message.

        :param message:
            A message with a structure as defined at
            https://core.telegram.org/bots/api#message
        """
        if message.text is None and message.new_chat_members == []:
            log.warning("Unhandled message type (not a text message) ignored")
            return
        message_instance = self.build_message(message.text or '')
        if message.chat['type'] == 'private':
            message_instance.frm = TelegramPerson(
                id=message.from_user.id,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                username=message.from_user.username
            )
            message_instance.to = self.bot_identifier
        else:
            room = TelegramRoom(id=message.chat.id, title=message.chat.title)
            message_instance.frm = TelegramMUCOccupant(
                id=message.from_user.id,
                room=room,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                username=message.from_user.username
            )
            message_instance.to = room
        message_instance.extras['message_id'] = message.message_id
        if message.new_chat_members:
            message_instance.extras['new_chat_members'] = (
                message.new_chat_members)
        self.callback_message(message_instance)

    def send_message(self, msg):
        super().send_message(msg)
        body = self.md_converter.convert(msg.body)
        try:
            self.telegram.sendMessage(msg.to.id, body)
        except Exception:
            log.exception(
                "An exception occurred while trying to send the following message "
                "to %s: %s" % (msg.to.id, msg.body)
            )
            raise

    def change_presence(self, status: str = ONLINE, message: str = '') -> None:
        # It looks like telegram doesn't supports online presence for privacy reason.
        pass

    def build_identifier(self, txtrep):
        """
        Convert a textual representation into a :class:`~TelegramPerson` or :class:`~TelegramRoom`.
        """
        log.debug("building an identifier from %s" % txtrep)
        if not self._is_numeric(txtrep):
            raise ValueError("Telegram identifiers must be numeric")
        id_ = int(txtrep)
        if id_ > 0:
            return TelegramPerson(id=id_)
        else:
            return TelegramRoom(id=id_)

    def build_reply(self, msg, text=None, private=False, threaded=False):
        response = self.build_message(text)
        response.frm = self.bot_identifier
        if private:
            response.to = msg.frm
        else:
            response.to = msg.frm if msg.is_direct else msg.to
        return response

    @property
    def mode(self):
        return 'telegram'

    def query_room(self, room):
        """
        Not supported on Telegram.

        :raises: :class:`~RoomsNotSupportedError`
        """
        raise RoomsNotSupportedError()

    def rooms(self):
        """
        Not supported on Telegram.

        :raises: :class:`~RoomsNotSupportedError`
        """
        raise RoomsNotSupportedError()

    def prefix_groupchat_reply(self, message, identifier):
        super().prefix_groupchat_reply(message, identifier)
        message.body = '@{0}: {1}'.format(identifier.nick, message.body)

    def _telegram_special_message(self, chat_id, content, msg_type, **kwargs):
        """Send special message."""
        if msg_type == 'document':
            msg = self.telegram.sendDocument(chat_id=chat_id,
                                             document=content,
                                             **kwargs)
        elif msg_type == 'photo':
            msg = self.telegram.sendPhoto(chat_id=chat_id,
                                          photo=content,
                                          **kwargs)

        elif msg_type == 'audio':
            msg = self.telegram.sendAudio(chat_id=chat_id,
                                          audio=content,
                                          **kwargs)

        elif msg_type == 'video':
            msg = self.telegram.sendVideo(chat_id=chat_id,
                                          video=content,
                                          **kwargs)
        elif msg_type == 'sticker':
            msg = self.telegram.sendSticker(chat_id=chat_id,
                                            sticker=content,
                                            **kwargs)
        elif msg_type == 'location':
            msg = self.telegram.sendLocation(chat_id=chat_id,
                                             latitude=kwargs.pop('latitude', ''),
                                             longitude=kwargs.pop('longitude', ''),
                                             **kwargs)
        else:
            raise ValueError('Expected a valid choice for `msg_type`, '
                             'got: {}.'.format(msg_type))
        return msg

    def _telegram_upload_stream(self, stream, **kwargs):
        """Perform upload defined in a stream."""
        msg = None
        try:
            stream.accept()
            msg = self._telegram_special_message(chat_id=stream.identifier.id,
                                                 content=stream.raw,
                                                 msg_type=stream.stream_type,
                                                 **kwargs)
        except Exception:
            log.exception("Upload of {0} to {1} failed.".format(stream.name,
                                                                stream.identifier))
        else:
            if msg is None:
                stream.error()
            else:
                stream.success()

    def send_stream_request(self, identifier, fsource, name='file', size=None, stream_type=None):
        """Starts a file transfer.

        :param identifier: TelegramPerson or TelegramMUCOccupant
            Identifier of the Person or Room to send the stream to.

        :param fsource: str, dict or binary data
            File URL or binary content from a local file.
            Optionally a dict with binary content plus metadata can be given.
            See `stream_type` for more details.

        :param name: str, optional
            Name of the file. Not sure if this works always.

        :param size: str, optional
            Size of the file obtained with os.path.getsize.
            This is only used for debug logging purposes.

        :param stream_type: str, optional
            Type of the stream. Choices: 'document', 'photo', 'audio', 'video', 'sticker', 'location'.

            If 'video', a dict is optional as {'content': fsource, 'duration': str}.
            If 'voice', a dict is optional as {'content': fsource, 'duration': str}.
            If 'audio', a dict is optional as {'content': fsource, 'duration': str, 'performer': str, 'title': str}.

            For 'location' a dict is mandatory as {'latitude': str, 'longitude': str}.
            For 'venue': TODO # see: https://core.telegram.org/bots/api#sendvenue

        :return stream: str or Stream
            If `fsource` is str will return str, else return Stream.
        """
        def _telegram_metadata(fsource):
            if isinstance(fsource, dict):
                return fsource.pop('content'), fsource
            else:
                return fsource, None

        def _is_valid_url(url):
            try:
                from urlparse import urlparse
            except Exception:
                from urllib.parse import urlparse

            return bool(urlparse(url).scheme)

        content, meta = _telegram_metadata(fsource)
        if isinstance(content, str):
            if not _is_valid_url(content):
                raise ValueError("Not valid URL: {}".format(content))

            self._telegram_special_message(chat_id=identifier.id,
                                           content=content,
                                           msg_type=stream_type,
                                           **meta)
            log.debug("Requesting upload of {0} to {1} (size hint: {2}, stream type: {3})".format(name,
                      identifier.username, size, stream_type))

            stream = content
        else:
            stream = Stream(identifier, content, name, size, stream_type)
            log.debug("Requesting upload of {0} to {1} (size hint: {2}, stream type: {3})".format(name,
                      identifier, size, stream_type))
            self.thread_pool.apply_async(self._telegram_upload_stream, (stream,))

        return stream

    @staticmethod
    def _is_numeric(input_):
        """Return true if input is a number"""
        try:
            int(input_)
            return True
        except ValueError:
            return False

    def delete_message(self, message):
        self.telegram.deleteMessage(
            message.frm.room.id, message.extras.message_id)
