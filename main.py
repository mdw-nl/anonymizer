from config_handler import Config
from consumer import Consumer
import logging


def anonymize(ch, method, properties, body, executor):
    logging.info(f"Received message: {body}")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger()

if __name__ == "__main__":
    rabbitMQ_config = Config("rabbitMQ")
    cons = Consumer(rmq_config=rabbitMQ_config)
    cons.open_connection_rmq()
    cons.start_consumer(callback=anonymize)