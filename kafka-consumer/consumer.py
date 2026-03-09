from confluent_kafka import Consumer, KafkaError
import json
import signal
import sys

running = True


def signal_handler(sig, frame):
    global running
    print("\nОстановка consumer...")
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

config = {
    'bootstrap.servers': 'kafka-0:9092',
    'group.id': 'python-consumer-group',
    'auto.offset.reset': 'earliest'
}

consumer = Consumer(config)

topics = ['cdc.public.users', 'cdc.public.orders']
consumer.subscribe(topics)

print(f"Подписались на топики: {topics}", flush=True)
print("Ожидание сообщений...\n", flush=True)

try:
    while running:
        msg = consumer.poll(timeout=1.0)

        if msg is None:
            continue

        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                print(f"--- Конец раздела {msg.topic()} [{msg.partition()}] ---", flush=True)
            else:
                print(f"Ошибка: {msg.error()}", flush=True)
            continue

        topic = msg.topic()
        key = msg.key().decode('utf-8') if msg.key() else None
        value = json.loads(msg.value().decode('utf-8'))

        print(f"{'=' * 60}", flush=True)
        print(f"Топик:  {topic}", flush=True)
        print(f"Ключ:   {key}", flush=True)
        print(f"Offset: {msg.offset()}", flush=True)

        payload = value.get('payload', value)

        op = payload.get('op', '?')
        op_names = {'c': 'INSERT', 'u': 'UPDATE', 'd': 'DELETE', 'r': 'READ (snapshot)'}
        print(f"Операция: {op_names.get(op, op)}", flush=True)

        if payload.get('before'):
            print(f"До:     {json.dumps(payload['before'], ensure_ascii=False, indent=2)}", flush=True)

        if payload.get('after'):
            print(f"После:  {json.dumps(payload['after'], ensure_ascii=False, indent=2)}", flush=True)

        print(flush=True)

finally:
    consumer.close()
    print("Consumer закрыт.", flush=True)
