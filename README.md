# WebRTC streaming server
WebRTC стриминговый сервер на языке **Python**

# Запуск
```
$ sudo docker-compose build
$ sudo docker-compose up
```

# Использование
 
 WebRTC взаимодействие с сервером доступно по [hostname/media/{id}]()
 где **id** - id камеры из https://nvr.miem.hse.ru/api/sources/
 
 Пример **[HTML](./media_server/templates/index.html)** и
 **[JS](./media_server/static/client.js)** 
 клиента
 
 Также пример клиента и проверка работоспособности сервера 
 доступны на https://media.auditory.ru/

