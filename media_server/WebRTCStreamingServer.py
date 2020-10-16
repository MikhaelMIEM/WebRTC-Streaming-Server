import argparse
import asyncio
import json
import logging
import ssl
import os

from aiohttp import web, ClientSession

from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaPlayer

NVR_TOKEN = os.environ.get('NVR_TOKEN')
if not NVR_TOKEN:
    raise NameError('Environment variable $NVR_TOKEN not found')

pcs = set()


class VideoTransformTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self, track):
        super().__init__()
        self.track = track

    async def recv(self):
        frame = await self.track.recv()
        frame = frame.reformat(width=320, height=240)
        return frame


async def get_streams():
    headers = {"key": NVR_TOKEN}

    async with ClientSession() as session:
        async with session.get('https://nvr.miem.hse.ru/api/sources/',
                               headers=headers) as resp:
            text = await resp.text()
            cams = json.loads(text)

    streams = {
        str(cam['id']): cam['rtsp']
        for cam in cams
    }
    streams['a'] = './a.mp4'
    streams['b'] = './b.webm'
    streams['c'] = './c.mp4'

    return streams


async def js_cors_preflight(request):
    request_url = request.match_info['stream']
    streams = await get_streams()

    if request_url not in streams:
        raise web.HTTPNotFound()
    headers = {
        'Access-Control-Allow-Origin': '*',
        "Access-Control-Allow-Headers": "Content-Type"
    }
    return web.Response(headers=headers, text="ok")


async def offer(request):
    request_url = request.match_info['stream']
    streams = await get_streams()

    if request_url not in streams:
        raise web.HTTPNotFound()

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

    play_from = streams[request_url]
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


async def on_shutdown(app):
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebRTC streaming server")
    parser.add_argument("--cert-file", help="SSL certificate file (for HTTPS)")
    parser.add_argument("--key-file", help="SSL key file (for HTTPS)")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host for server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8181, help="Server port (default: 8181)"
    )
    parser.add_argument("--verbose", "-v", action="count")
    args = parser.parse_args()

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

    web.run_app(app, host=args.host, port=args.port, ssl_context=ssl_context)
