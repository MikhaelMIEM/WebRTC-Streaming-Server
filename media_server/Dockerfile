FROM python:3.8.6
COPY . ./
ARG PORT=${PORT}
ARG NVR_TOKEN=${NVR_TOKEN}
ARG SSL_KEY=${SSL_KEY}
ARG SSL_CERT=${SSL_CERT}
RUN pip install -r ./requirements.txt
CMD python WebRTCStreamingServer.py --port ${PORT} --nvr-token ${NVR_TOKEN} --key-file ${SSL_KEY} --cert-file ${SSL_CERT}