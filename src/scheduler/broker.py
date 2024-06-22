from taskiq import InMemoryBroker


def create_broker() -> InMemoryBroker:
    return InMemoryBroker()
