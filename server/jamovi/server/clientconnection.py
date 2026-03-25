#
# Copyright (C) 2016 Jonathon Love
#

from .session import NoSuchInstanceException

from tornado.websocket import WebSocketHandler

from . import jamovi_pb2 as coms
from .jamovi_pb2 import ComsMessage
from .jamovi_pb2 import Status as MessageStatus
from .jamovi_pb2 import InstanceRequest
from .jamovi_pb2 import InstanceResponse

from jamovi.server.utils import conf

import asyncio
import hmac
import hashlib
import os
import time
import logging
import urllib.parse

log = logging.getLogger(__name__)

# HeyStat classroom: shared secret for verifying collab_role tokens issued by LMS API.
# Set JAMOVI_COLLAB_SECRET env var on both the HeyStat container and the LMS API container.
_COLLAB_SECRET = os.environ.get('JAMOVI_COLLAB_SECRET', '')


def _verify_collab_token(token_str: str) -> str:
    """Verify a collab token and return the role ('writer' or 'observer').

    Token format: ``{role}.{expiry_unix}.{hmac_hex}``

    Returns 'writer' on any verification failure so the connection degrades
    gracefully rather than blocking legitimate users.
    """
    if not _COLLAB_SECRET or not token_str:
        return 'writer'
    try:
        parts = token_str.split('.')
        if len(parts) != 3:
            return 'writer'
        role, expiry_str, provided_sig = parts
        if role not in ('writer', 'observer'):
            return 'writer'
        expiry = int(expiry_str)
        if expiry < int(time.time()):
            log.debug('collab_token expired')
            return 'writer'
        payload = f'{role}:{expiry_str}'
        expected_sig = hmac.new(
            _COLLAB_SECRET.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_sig, provided_sig):
            log.warning('collab_token HMAC mismatch – defaulting to writer')
            return 'writer'
        return role
    except Exception:
        return 'writer'


class ClientConnection(WebSocketHandler):

    number_of_connections = 0

    def initialize(self, session):

        self._session = session
        self._transactions = { }
        self._close_listeners = [ ]
        self._instance_id = None
        self._collab_role = 'writer'  # HeyStat classroom: 'writer' | 'observer'

    def check_origin(self, origin):
        return True

    def open(self, instance_id):
        key_required = conf.get('access_key', '')
        if key_required != '':
            if key_required != self.get_cookie('access_key', None):
                self.close()

        # HeyStat classroom: extract collab_role from the ?collab_token= query parameter.
        # The token is signed by the LMS API with JAMOVI_COLLAB_SECRET.
        query_str = self.request.query or ''
        params = urllib.parse.parse_qs(query_str)
        collab_token = params.get('collab_token', [None])[0]
        self._collab_role = _verify_collab_token(collab_token)

        log.debug('%s', 'Websocket opened')
        self._instance_id = instance_id
        ClientConnection.number_of_connections += 1
        self.set_nodelay(True)

    def on_close(self):
        log.debug('%s %s %s', 'Websocket closed', self.close_code, self.close_reason)
        ClientConnection.number_of_connections -= 1
        for listener in self._close_listeners:
            # close_code comes through as None when it's not a clean disconnection
            # we treat it special because electron shuts down the websocket uncleanly
            # when the computer goes to sleep, and we don't want to garbage collect
            # the instance in that situation
            listener(self.close_code is not None)

    def on_message(self, m_bytes):
        asyncio.ensure_future(self.on_message_async(m_bytes))

    async def on_message_async(self, m_bytes):
        try:
            message = ComsMessage()
            message.ParseFromString(m_bytes)
            if not message.payloadType:
                # should log bad request
                return
            clas = getattr(coms, message.payloadType)
            request = clas()
            request.ParseFromString(message.payload)
            self._transactions[message.id] = request

            if type(request) == InstanceRequest:
                if message.instanceId == '':
                    instance = self._session.create()  # create new
                elif message.instanceId not in self._session:
                    raise NoSuchInstanceException()
                else:
                    instance = self._session[message.instanceId]
                instance.set_coms(self, role=self._collab_role)
                response = InstanceResponse()
                response.instanceId = instance.id
                self.send(response, instance.id, request)
            else:
                instance = self._session[message.instanceId]
                instance.set_coms(self, role=self._collab_role)
                # HeyStat classroom: observers receive broadcasts but cannot send write requests
                if self._collab_role == 'observer':
                    return
                await instance.on_request(request)
        except NoSuchInstanceException:
            self.send_error(
                message='No such instance',
                instance_id=message.instanceId,
                response_to=request)
        except Exception as e:
            # would be nice to send_error()
            log.exception(e)

    def send(self, message=None, instance_id=None, response_to=None,
             complete=True, progress=(0, 0), status=None):

        if message is None and response_to is None:
            return

        m = ComsMessage()

        if instance_id is not None:
            m.instanceId = instance_id

        if response_to is not None:
            for key, value in self._transactions.items():
                if value is response_to:
                    m.id = key
                    if complete:
                        del self._transactions[key]
                    break
        else:
            m.id = 0

        if message is not None:
            m.payload = message.SerializeToString()
            m.payloadType = message.__class__.__name__

        if status is not None:
            m.error.message, m.error.cause = status

        if complete:
            m.status = MessageStatus.Value('COMPLETE')
        else:
            m.status = MessageStatus.Value('IN_PROGRESS')

        m.progress = int(progress[0])
        m.progressTotal = int(progress[1])

        return self.write_message(m.SerializeToString(), binary=True)

    def send_error(self, message=None, cause=None, instance_id=None, response_to=None):

        m = ComsMessage()

        if instance_id is not None:
            m.instanceId = instance_id

        if response_to is not None:
            for key, value in self._transactions.items():
                if value is response_to:
                    m.id = key
                    del self._transactions[key]
                    break
        else:
            m.id = 0

        if message is not None:
            m.error.message = message

        if cause is not None:
            m.error.cause = cause

        m.status = MessageStatus.Value('ERROR')

        self.write_message(m.SerializeToString(), binary=True)

    def add_close_listener(self, listener):
        self._close_listeners.append(listener)

    def remove_close_listener(self, listener):
        self._close_listeners.remove(listener)

    def discard(self, message):
        for key, value in self._transactions.items():
            if value is message:
                del self._transactions[key]
                break
