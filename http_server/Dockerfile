FROM python:3.8.6-alpine

ARG KEY_PATH=./privkey.pem
ARG CERT_PATH=./fullchain.pem

COPY . ./
COPY ${SSL_KEY} ${KEY_PATH}
COPY ${SSL_CERT} ${CERT_PATH}

RUN pip install -r ./requirements.txt
CMD python main.py -p ${PORT} --nvr-token ${NVR_TOKEN} --ssl-key ${KEY_PATH} --ssl-cert ${CERT_PATH}