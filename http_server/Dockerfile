FROM python:3.8.6-alpine
COPY . ./
ENV PORT=${PORT}
ENV NVR_TOKEN=${NVR_TOKEN}
ENV SSL_KEY=${SSL_KEY}
ENV SSL_CERT=${SSL_CERT}
RUN pip install -r ./requirements.txt
CMD python main.py -p $PORT --nvr-token $NVR_TOKEN --ssl-key $SSL_KEY --ssl-cert $SSL_CERT