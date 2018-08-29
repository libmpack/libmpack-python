import asyncio
import collections

import mpack


class ErrorResponse(Exception):
    pass


class Message(object):
    def __init__(self, method, args, id, session, writer):
        self.method = method
        self.args = args
        self._id = id
        self._session = session
        self._writer = writer

    def __repr__(self):
        t = 'notification' if self.is_notification else 'request'
        return '{}, ({}: {})'.format(t, self.method, self.args)

    @property
    def is_notification(self):
        return self._id is None

    def reply(self, result, error=False):
        if self.is_notification:
            raise Exception('Cannot reply to a notification')
        response_data = self._session.reply(self._id, result, error)
        self._writer.write(response_data)
        return self._writer.drain()


class Session(object):
    def __init__(self, reader, writer, mpack_session=None):
        self._reader = reader
        self._writer = writer
        self._session = mpack_session or mpack.Session()
        # FIXME _loop is a private member of StreamReader, but it also seems
        # redundant to accept an extra loop parameter since reader/writer are
        # already associated with loop. Maybe there's a cleaner way?
        self._loop = reader._loop
        self._message_queue = collections.deque()
        self._poll_conditions = set()
        self._polling = False
        self._buf = None

    async def _read(self):
        if self._buf:
            rv = self._buf
            self._buf = None
            return rv
        else:
            if self._reader.at_eof():
                raise Exception('Connection was closed')
            return await self._reader.read(0xfff)

    async def _receive(self):
        msg_type = None
        while not msg_type:
            chunk = await self._read()
            if not chunk:
                return
            offs, msg_type, name_or_err, args_or_result, id_or_data = (
                    self._session.receive(chunk))
            if not msg_type:
                continue
            chunk = chunk[offs:]
            if chunk:
                # received more than one message, save the extra chunk for
                # later
                self._buf = chunk
            if msg_type == 'response':
                # set the result of the saved future
                assert isinstance(id_or_data, asyncio.Future) 
                if name_or_err:
                    id_or_data.set_exception(ErrorResponse(*name_or_err))
                else:
                    id_or_data.set_result(args_or_result)
            else:
                assert msg_type in ['request', 'notification']
                # enqueue the message for later processing
                self._message_queue.append(Message(name_or_err, args_or_result,
                    id_or_data, self._session, self._writer))

    async def _poll(self):
        assert not self._polling
        self._polling = True
        while True:
            to_remove = []
            for cond in self._poll_conditions:
                if not cond[0]() or self._reader.at_eof():
                    cond[1].set_result(None)
                    to_remove.append(cond)
            for cond in to_remove:
                self._poll_conditions.remove(cond)
            if not self._poll_conditions:
                break
            await self._receive()
        self._polling = False

    def _poll_while(self, condition):
        future = asyncio.Future(loop=self._loop)
        self._poll_conditions.add((condition, future))
        if not self._polling and len(self._poll_conditions) == 1:
            self._loop.create_task(self._poll())
        return future

    async def next_message(self):
        await self._poll_while(lambda: not self._message_queue)
        return self._message_queue.popleft() if self._message_queue else None

    async def request(self, method, *args):
        future = asyncio.Future(loop=self._loop)
        request_data = self._session.request(method, args, data=future)
        self._writer.write(request_data)
        await self._poll_while(lambda: not future.done())
        if not future.done():
            raise Exception('Connection closed before response arrived')
        return future.result()

    async def notify(self, method, *args):
        notification_data = self._session.notify(method, args)
        self._writer.write(notification_data)
        future = asyncio.ensure_future(self._writer.drain())
        await self._poll_while(lambda: not future.done())
        if not future.done():
            raise Exception('Connection closed before notification was sent')

    def close(self):
        self._writer.close()
