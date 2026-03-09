# Debezium Connector

## Описание проекта
Debezium Connector для передачи данных из базы данных PostgreSQL в Apache Kafka с использованием механизма Change Data Capture (CDC).

## Технологии

- Python
- Kafka
- FastApi
- Docker
- Docker Compose

## Запуск проекта

- клонируйте репозиторий на локальную машину и перейдите в созданную папку:

''' git clone git@github.com:son13425/kafka-debezium-connector.git'''

- установите Docker (Зайдите на официальный сайт https://www.docker.com/products/docker-desktop и скачайте установочный файл Docker Desktop для вашей операционной системы)

- проверьте, что Docker работает:

'''sudo systemctl status docker'''

- выполните команду в директории проекта

'''sudo docker-compose up -d --build'''

- приложение разворачивается локально и становится доступным по адресам:

  - http://localhost:3000 - Grafana — веб-интерфейс для визуализации метрик. Логин: admin, пароль: admin. Здесь находится дашборд «Kafka CDC Debezium — Мониторинг» с графиками скорости сообщений, распределением операций INSERT/UPDATE/DELETE, статусом Consumer и детализацией по таблицам.;

  - http://localhost:8085/metrics - Kafka Prometheus Connector — эндпоинт метрик. Отдаёт метрики в текстовом формате Prometheus (counters, gauges): количество сообщений по топикам, операции по типам, ошибки consumer, timestamp последнего сообщения. Именно сюда ходит Prometheus за данными.;

  - http://localhost:8085/health - Kafka Prometheus Connector — healthcheck. Возвращает JSON со статусом сервиса и флагом consumer_running, показывающим, работает ли фоновый Kafka Consumer.;

  - http://localhost:8085/docs - Kafka Prometheus Connector — Swagger UI. Автоматически сгенерированная FastAPI интерактивная документация API, где можно посмотреть все эндпоинты и выполнить тестовые запросы прямо из браузера.;

  - http://localhost:8085/redoc - Kafka Prometheus Connector — ReDoc. Альтернативная документация API в формате ReDoc — более компактное и читаемое представление спецификации OpenAPI.;

  - http://localhost:9090 - Prometheus — веб-интерфейс для работы с метриками. Во вкладке Graph можно писать PromQL-запросы (например, kafka_messages_total, rate(kafka_insert_total[5m])). Во вкладке Status → Targets видно состояние подключения к Kafka Prometheus Connector (UP/DOWN).;

  - http://localhost:8080 - Kafka Connect UI (Kafka Connect REST + UI) — веб-интерфейс для управления коннекторами Debezium. Здесь можно видеть зарегистрированные CDC-коннекторы, их статус, конфигурацию, а также создавать и удалять коннекторы.;

  - http://localhost:8082 - Kafka UI — веб-интерфейс для Кафка.


## Тест проекта

- Создайте таблицы в БД:

'''docker exec -it postgres psql -h 127.0.0.1 -U postgres-user -d customers'''

'''CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);'''

'''CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    product_name VARCHAR(100),
    quantity INT,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);'''

- Создайте коннектор:

'''curl -X POST http://localhost:8083/connectors -H "Content-Type: application/json" -d "{
  \"name\": \"postgres-debezium-connector\",
  \"config\": {
    \"connector.class\": \"io.debezium.connector.postgresql.PostgresConnector\",
    \"tasks.max\": \"1\",
    \"database.hostname\": \"postgres\",
    \"database.port\": \"5432\",
    \"database.user\": \"postgres-user\",
    \"database.password\": \"postgres-pw\",
    \"database.dbname\": \"customers\",
    \"topic.prefix\": \"cdc\",
    \"schema.include.list\": \"public\",
    \"table.include.list\": \"public.users,public.orders\",
    \"plugin.name\": \"pgoutput\",
    \"publication.autocreate.mode\": \"filtered\",
    \"slot.name\": \"debezium_slot\",
    \"publication.name\": \"debezium_publication\",
    \"key.converter\": \"org.apache.kafka.connect.json.JsonConverter\",
    \"key.converter.schemas.enable\": \"false\",
    \"value.converter\": \"org.apache.kafka.connect.json.JsonConverter\",
    \"value.converter.schemas.enable\": \"false\"
  }
}"'''

- Наполни таблицы данными:

'''docker exec -it postgres psql -U postgres-user -d customers -c "
INSERT INTO users (name, email) VALUES ('John Doe', 'john@example.com');
INSERT INTO users (name, email) VALUES ('Jane Smith', 'jane@example.com');
INSERT INTO users (name, email) VALUES ('Alice Johnson', 'alice@example.com');
INSERT INTO users (name, email) VALUES ('Bob Brown', 'bob@example.com');
INSERT INTO orders (user_id, product_name, quantity) VALUES (1, 'Product A', 2);
INSERT INTO orders (user_id, product_name, quantity) VALUES (1, 'Product B', 1);
INSERT INTO orders (user_id, product_name, quantity) VALUES (2, 'Product C', 5);
INSERT INTO orders (user_id, product_name, quantity) VALUES (3, 'Product D', 3);
INSERT INTO orders (user_id, product_name, quantity) VALUES (4, 'Product E', 4);
INSERT INTO users (name, email) VALUES ('Test1', 'test1@test.com');
INSERT INTO users (name, email) VALUES ('Test2', 'test2@test.com');
INSERT INTO orders (user_id, product_name, quantity) VALUES (1, 'Monitor', 1);
UPDATE users SET email = 'updated@test.com' WHERE name = 'Test1';
DELETE FROM orders WHERE product_name = 'Monitor';
"'''

- Проверяем топики в Kafka UI:

Открыть http://localhost:8082 в браузере, перейти в раздел Topics. Должны быть топики:
cdc.public.users — события из таблицы users
cdc.public.orders — события из таблицы orders
Перейти в топик → Messages → увидишь JSON с полями before, after, op (тип операции: c — create, u — update, d — delete).

- Смотрим логи consumer:

'''docker-compose logs -f kafka-consumer'''

Должны быть сообщения из топиков.

- Проверяем Prometheus UI:

Открыть http://localhost:9090, перейти в Status → Targets — там должен быть таргет kafka-prometheus-connector в состоянии UP. В разделе Graph можно запросить, например, kafka_messages_total или kafka_insert_total и увидеть графики.

- Проверям Grafana:

Открыть http://localhost:3000 в браузере.
Логин: admin, пароль: admin.
Перейти в Dashboards → Kafka CDC → Kafka CDC Debezium — Мониторинг.

Дашборд с панелями:

Верхний ряд (статусы): индикатор работоспособности Consumer (зелёный/красный), счётчик ошибок, общее количество обработанных сообщений, разбивка по топикам.

Средний ряд (графики): скорость получения сообщений (msg/sec) по топикам с гладкими линиями, а рядом — столбчатая диаграмма с операциями INSERT/UPDATE/DELETE, сгруппированными по типу.

Нижний ряд (аналитика): круговая диаграмма (donut) распределения операций, горизонтальный bar gauge записей по таблицам, и таблица с детализацией INSERT/UPDATE/DELETE по каждой таблице.

Самый низ: таймлайн последнего полученного сообщения по каждому топику.


## Автор
[Оксана Широкова](https://github.com/son13425)

## Лицензия
Сценарии и документация в этом проекте выпущены под лицензией [MIT](https://github.com/son13425/kafka-project/blob/main/LICENSE)
