import pika
import logging
import concurrent.futures
import time
import threading


class Consumer:
    def __init__(self, rmq_config):
        self.connection_rmq = None
        self.channel = None
        self.config_dict_rmq = rmq_config.config
        self.db = None
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        self.stop_heartbeat = threading.Event()

    def open_connection_rmq(self):
        """Establish connection"""
        host, port, user, pwd = self.config_dict_rmq["host"], self.config_dict_rmq["port"] \
            , self.config_dict_rmq["username"], self.config_dict_rmq["password"]

        connection_string = f"amqp://{user}:{pwd}@{host}:{port}/"
        connection = pika.BlockingConnection(pika.URLParameters(connection_string))
        self.connection_rmq = connection
        self.channel = self.connection_rmq.channel()
        heartbeat_thread = threading.Thread(target=self.send_heartbeats, daemon=True)
        heartbeat_thread.start()

    def send_heartbeats(self):
        """Send periodic heartbeats to keep the connection alive"""
        while not self.stop_heartbeat.is_set():
            try:
                logging.info("Sending heartbeat..")
                self.connection_rmq.process_data_events()
                logging.info("Heartbeat sent.")
            except Exception as e:
                print(f"Heartbeat error: {e}")
            time.sleep(10)

    def close_connection(self):
        """Close connection"""

        self.connection_rmq.close()

    def start_consumer(self, callback):
        self.channel.basic_consume(queue=self.config_dict_rmq["queue_name"],
                                   on_message_callback=lambda ch, method, properties, body: callback(ch, method,
                                                                                                     properties, body,
                                                                                                     self.executor),
                                   auto_ack=False)
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            print("Consumer stopped by user.")
        finally:
            self.executor.shutdown(wait=True)