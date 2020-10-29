import logging
import argparse
import asyncio
import json
import ssl
import os
from urllib.parse import urlparse

from aiohttp import web, ClientSession
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaPlayer
import aiohttp_jinja2 as aiojinja2
import jinja2


args = None
pcs = set()


def get_arguments():
    parser = argparse.ArgumentParser(description="WebRTC streaming server")
    parser.add_argument("--cert-file", help="SSL certificate file (for HTTPS)")
    parser.add_argument("--key-file", help="SSL key file (for HTTPS)")
    parser.add_argument("--host", default="0.0.0.0", help="Host for server (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8181, help="Server port (default: 8181)")
    parser.add_argument("--nvr-token", help="NVR api token", required=True)
    parser.add_argument("--verbose", "-v", action="count")
    return parser.parse_args()


class VideoTransformTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self, track):
        super().__init__()
        self.track = track

    async def recv(self):
        frame = await self.track.recv()
        frame = frame.reformat(width=320, height=240)
        return frame


async def offer(request):
    request_url = request.match_info['stream']
    streams = await get_streams(args.nvr_token)

    if request_url not in streams:
        raise web.HTTPNotFound(text='No rtsp source related to this url')

    play_from = streams[request_url]
    if not play_from:
        raise web.HTTPBadGateway(text='NVR response with cam rtsp link is empty. Contact NVR admins to fix it')

    url = urlparse(play_from)
    if url.scheme == 'rtsp':
        await check_rtsp_availability(play_from, timeout=10)

    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        print("ICE connection state is %s" % pc.iceConnectionState)
        if pc.iceConnectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    player = MediaPlayer(play_from)

    await pc.setRemoteDescription(offer)
    for t in pc.getTransceivers():
        if t.kind == "audio" and player.audio:
            pc.addTrack(player.audio)
        elif t.kind == "video" and player.video:
            track = VideoTransformTrack(player.video)
            pc.addTrack(track)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        headers={
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type',
        },
        text=json.dumps({
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        })
    )


async def js_cors_preflight(request):
    headers = {
        'Access-Control-Allow-Origin': '*',
        "Access-Control-Allow-Headers": "Content-Type"
    }
    return web.Response(headers=headers, text="ok")


async def get_cams(nvr_token):
    headers = {"key": nvr_token}

    async with ClientSession() as session:
        async with session.get('https://nvr.miem.hse.ru/api/sources/',
                               headers=headers) as resp:
            text = await resp.text()
            cams = json.loads(text)
    cams.append({'id': 'test', 'rtsp': './test.webm'})
    return cams


async def get_streams(nvr_token):
    cams = await get_cams(nvr_token)
    streams = {
        str(cam['id']): cam['rtsp']
        for cam in cams
    }
    return streams

async def check_rtsp_availability(rtsp_link, timeout):
    """
    This function needed because some rtsp links requires
    to authenticate and pyav lib may freeze in such cases.
    If some rtsp link require authentication contact NVR admins to replace it with working link.
    """
    url = urlparse(rtsp_link)
    ip = url.hostname
    port = url.port if url.port else 554
    reader = None
    writer = None

    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=timeout)
        is_available = bool(reader) and bool(writer)
    except asyncio.TimeoutError:
        raise web.HTTPBadGateway(text='Can not establish connection with rtsp media source')
    except OSError:
        raise web.HTTPBadGateway(text='Can not establish connection with rtsp media source')
    finally:
        if writer:
            writer.close()
            await writer.wait_closed()

    if not is_available:
        raise web.HTTPBadGateway(text='Can not establish connection with rtsp media source')

    # message = f'DESCRIBE {rtsp_link} RTSP/1.0\nCSeq: 1\n\n'
    # writer.write(message.encode())
    # await writer.drain()
    #
    # data = await reader.read(1000)
    # writer.close()
    # await writer.wait_closed()
    #
    # describe_reply = data.decode().split()
    # if describe_reply[1] == '401':
    #     raise web.HTTPBadGateway(text='rtsp stream require authentication')


async def on_shutdown(app):
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


@aiojinja2.template('index.html')
async def index(request):
    cams = await get_cams(args.nvr_token)
    return {'cams': cams}





if __name__ == "__main__":
    args = get_arguments()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    if args.cert_file:
        ssl_context = ssl.SSLContext()
        ssl_context.load_cert_chain(args.cert_file, args.key_file)
    else:
        ssl_context = None

    media = web.Application()
    media.router.add_post("/{stream}", offer)
    media.router.add_options("/{stream}", js_cors_preflight)

    app = web.Application()
    app.add_subapp("/media/", media)
    app.on_shutdown.append(on_shutdown)

    aiojinja2.setup(app, loader=jinja2.FileSystemLoader('/templates/'))
    app.router.add_get('/', index)
    app.router.add_static('/static/', path='/static')

    web.run_app(app, host=args.host, port=args.port, ssl_context=ssl_context)
