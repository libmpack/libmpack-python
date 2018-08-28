# TODO: rewrite these tests to not depend on neovim, or modify .travis.yml to
# install neovim and run these tests for python 3.5+
import asyncio

from mpack.asyncio import Session, ErrorResponse


cid = None
notifications = []
reply = [1, '2']



async def factorial(nvim, msg):
    n = msg.args[0]
    if n == 1:
        await msg.reply(1) 
    else:
        n2 = n - 1
        rv = await nvim.request('nvim_eval',
                'rpcrequest({}, "factorial", {})'.format(cid, n2))
        await msg.reply(n * rv)


async def request_handler(nvim):
    while True:
        msg = await nvim.next_message()
        if not msg:
            break  # eof
        if msg.is_notification:
            notifications.append(msg)
            continue
        if msg.method == 'factorial':
            # when handling requests that can result in cross-ipc recursion,
            # create a separate task to handle it or we may deadlock
            asyncio.get_event_loop().create_task(factorial(nvim, msg))
        else:
            await msg.reply(reply + [msg.method])


async def test_request(nvim):
    assert await nvim.request('nvim_eval', '3 + 3') == 6


async def test_exception(nvim):
    try:
        await nvim.request('invalid_method')
        assert False
    except Exception as e:
        code, msg = e.args
        assert code == 0
        assert msg == 'Invalid method name'


async def request_handling_tests(nvim):
    assert await nvim.request('nvim_eval',
            'rpcrequest({}, "test")'.format(cid)) == [1, '2', 'test']
    # test recursion
    assert await nvim.request('nvim_eval',
            'rpcrequest({}, "factorial", 12)'.format(cid)) == 479001600
    # # receive notification
    assert len(notifications) == 0
    await nvim.request('nvim_eval',
            'rpcnotify({}, "factorial", 12, 13)'.format(cid))
    assert len(notifications) == 1
    assert notifications[0].method == 'factorial'
    assert notifications[0].args == [12, 13]
    await nvim.notify('nvim_command', 'q!')


async def run():
    global cid
    proc = await asyncio.create_subprocess_exec(
            'nvim', '-u', 'NONE', '--embed',
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE)
    reader, writer = proc.stdout, proc.stdin
    nvim = Session(reader, writer)
    cid, _ = await nvim.request('vim_get_api_info')
    # tests
    await test_request(nvim)
    await test_exception(nvim)
    # request/notification handling tests
    await asyncio.gather(request_handling_tests(nvim), request_handler(nvim))
    # quit
    await proc.wait()


def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
    loop.close()


if __name__ == '__main__':
    main()


