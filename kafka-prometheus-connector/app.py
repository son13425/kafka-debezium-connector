import json
import threading
import time
import signal
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from confluent_kafka import Consumer, KafkaError
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from jinja2 import Template


# ---------------------------------------------------------------------------
# Загрузка конфигурации из config.json
# ---------------------------------------------------------------------------
config_path = Path(__file__).parent / "config.json"
with open(config_path) as f:
    connector_config = json.load(f)

KAFKA_BOOTSTRAP = connector_config["config"][
    "confluent.topic.bootstrap.servers"
]
TOPICS = [t.strip() for t in connector_config["config"]["topics"].split(",")]


# ---------------------------------------------------------------------------
# Хранилище метрик (потокобезопасное через GIL + простые операции)
# ---------------------------------------------------------------------------
@dataclass
class OperationKey:
    topic: str
    operation: str

    def __hash__(self):
        return hash((self.topic, self.operation))

    def __eq__(self, other):
        return self.topic == other.topic and self.operation == other.operation


class MetricsStore:
    def __init__(self):
        self.messages_total: dict[str, int] = defaultdict(int)
        self.operations_total: dict[OperationKey, int] = defaultdict(int)
        self.last_message_ts: dict[str, float] = {}
        self.consumer_errors: int = 0
        self.consumer_running: int = 0
        self.records_per_table: dict[str, int] = defaultdict(int)
        self.inserts_per_table: dict[str, int] = defaultdict(int)
        self.updates_per_table: dict[str, int] = defaultdict(int)
        self.deletes_per_table: dict[str, int] = defaultdict(int)
        self.lock = threading.Lock()

    def record_message(self, topic: str, operation: str):
        """Записывает факт получения сообщения из Kafka."""
        # Извлекаем имя таблицы из топика (cdc.public.users -> users)
        table = topic.split(".")[-1] if "." in topic else topic
        now = time.time()

        with self.lock:
            self.messages_total[topic] += 1
            self.operations_total[OperationKey(topic, operation)] += 1
            self.last_message_ts[topic] = now
            self.records_per_table[table] += 1

            if operation == "INSERT":
                self.inserts_per_table[table] += 1
            elif operation == "UPDATE":
                self.updates_per_table[table] += 1
            elif operation == "DELETE":
                self.deletes_per_table[table] += 1

    def record_error(self):
        with self.lock:
            self.consumer_errors += 1

    def set_running(self, running: bool):
        with self.lock:
            self.consumer_running = 1 if running else 0

    def snapshot(self) -> dict:
        """Возвращает снимок всех метрик для рендеринга шаблона."""
        with self.lock:
            return {
                "messages_total": dict(self.messages_total),
                "operations_total": dict(self.operations_total),
                "last_message_ts": dict(self.last_message_ts),
                "consumer_errors": self.consumer_errors,
                "consumer_running": self.consumer_running,
                "records_per_table": dict(self.records_per_table),
                "inserts_per_table": dict(self.inserts_per_table),
                "updates_per_table": dict(self.updates_per_table),
                "deletes_per_table": dict(self.deletes_per_table),
            }


store = MetricsStore()


# ---------------------------------------------------------------------------
# Загрузка Jinja2-шаблона метрик
# ---------------------------------------------------------------------------
template_path = Path(__file__).parent / "metrics_template.j2"
with open(template_path) as f:
    metrics_template = Template(f.read())


# ---------------------------------------------------------------------------
# Kafka Consumer (фоновый поток)
# ---------------------------------------------------------------------------
OP_NAMES = {"c": "INSERT", "u": "UPDATE", "d": "DELETE", "r": "READ"}

running = True


def signal_handler(sig, frame):
    global running
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def kafka_consumer_loop():
    """Основной цикл чтения из Kafka — работает в отдельном потоке."""
    global running

    consumer_config = {
        "bootstrap.servers": KAFKA_BOOTSTRAP,
        "group.id": "prometheus-connector-group",
        "auto.offset.reset": "earliest",
    }

    consumer = Consumer(consumer_config)
    consumer.subscribe(TOPICS)
    store.set_running(True)

    print(f"[Consumer] Подписались на топики: {TOPICS}", flush=True)
    print("[Consumer] Ожидание сообщений...\n", flush=True)

    try:
        while running:
            msg = consumer.poll(timeout=1.0)

            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                print(f"[Consumer] Ошибка: {msg.error()}", flush=True)
                store.record_error()
                continue

            topic = msg.topic()

            try:
                value = json.loads(msg.value().decode("utf-8"))
                payload = value.get("payload", value)
                op_code = payload.get("op", "?")
                operation = OP_NAMES.get(op_code, "UNKNOWN")
            except (json.JSONDecodeError, AttributeError):
                operation = "UNKNOWN"

            store.record_message(topic, operation)

            print(
                f"[Consumer] topic={topic} op={operation} offset={msg.offset()}",
                flush=True,
            )

    finally:
        store.set_running(False)
        consumer.close()
        print("[Consumer] Consumer закрыт.", flush=True)


# ---------------------------------------------------------------------------
# FastAPI — HTTP-эндпоинт /metrics
# ---------------------------------------------------------------------------
app = FastAPI(title="Kafka Prometheus Connector")


@app.on_event("startup")
def start_consumer_thread():
    """Запуск Kafka Consumer в фоновом потоке при старте FastAPI."""
    thread = threading.Thread(target=kafka_consumer_loop, daemon=True)
    thread.start()
    print("[App] Kafka consumer thread запущен", flush=True)


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    """
    Эндпоинт для Prometheus.
    Prometheus обращается сюда и получает метрики в текстовом формате.
    Временные метки не передаются — Prometheus использует время опроса.
    """
    data = store.snapshot()

    try:
        output = metrics_template.render(**data)
    except Exception as e:
        print(
            f"[App] Ошибка рендеринга шаблона: {e}",
            flush=True,
            file=sys.stderr
        )
        return PlainTextResponse(
            f"# Ошибка рендеринга метрик: {e}\n", status_code=500
        )

    return output


@app.get("/health")
def health():
    return {"status": "ok", "consumer_running": bool(store.consumer_running)}
