import asyncio
from urllib.parse import urlparse


async def stream_require_authentication(rtsp_link) -> bool:
    url = urlparse(rtsp_link)
    ip = url.hostname
    port = url.port if url.port else 554
    reader = None
    writer = None

    reader, writer = await asyncio.open_connection(ip, port)

    message = f'DESCRIBE {rtsp_link} RTSP/1.0\nCSeq: 1\n\n'
    print(f'Send: {message}')
    writer.write(message.encode())
    await writer.drain()

    data = await reader.read(100)
    writer.close()
    await writer.wait_closed()

    describe_reply = data.decode().split()
    return describe_reply[1] == '401'


async def connection_available(rtsp_link, *, timeout=10) -> bool:
    url = urlparse(rtsp_link)
    ip = url.hostname
    port = url.port if url.port else 554
    is_available = False
    reader = None
    writer = None
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=timeout)
        is_available = bool(reader) and bool(writer)
    except asyncio.TimeoutError:
        is_available = False
    except OSError:
        is_available = False
    finally:
        if writer:
            writer.close()
            await writer.wait_closed()
    return is_available
