FROM python:3.8.6
COPY . ./
RUN pip install -r ./requirements.txt
CMD python WebRTCStreamingServer.py --port ${PORT} --nvr-token ${NVR_TOKEN} --key-file ${SSL_KEY} --cert-file ${SSL_CERT}