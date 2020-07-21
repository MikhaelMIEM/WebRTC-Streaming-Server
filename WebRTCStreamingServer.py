import argparse
import asyncio
import json
import logging
import ssl

from aiohttp import web

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer

logger = logging.getLogger(__name__)
pcs = set()
streams = {
    "cam52": "rtsp://admin:Supervisor@172.18.200.52",
    "cam53": "rtsp://admin:Supervisor@172.18.200.53",
    "cam17": "rtsp://admin:Supervisor@172.18.212.17"
}


async def js_cors_preflight(request):
    stream = request.match_info['stream']
    if stream not in streams:
        raise web.HTTPNotFound()
    headers = {
        'Access-Control-Allow-Origin': '*',
        "Access-Control-Allow-Headers": "Content-Type"
    }
    return web.Response(headers=headers, text="ok")


async def offer(request):
    stream = request.match_info['stream']
    if stream not in streams:
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

    play_from = streams[stream]
    player = MediaPlayer(play_from)

    await pc.setRemoteDescription(offer)
    for t in pc.getTransceivers():
        if t.kind == "audio" and player.audio:
            pc.addTrack(player.audio)
        elif t.kind == "video" and player.video:
            pc.addTrack(player.video)

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
