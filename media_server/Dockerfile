FROM python:3.8.6

ARG KEY_PATH=./privkey.pem
ARG CERT_PATH=./fullchain.pem

COPY . ./
COPY ${SSL_KEY} ${KEY_PATH}
COPY ${SSL_CERT} ${CERT_PATH}

RUN pip install -r ./requirements.txt
CMD python WebRTCStreamingServer.py --port ${PORT} --nvr-token ${NVR_TOKEN} --key-file ${KEY_PATH} --cert-file ${CERT_PATH}