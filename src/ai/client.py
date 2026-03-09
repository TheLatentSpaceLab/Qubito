
from abc import abstractmethod


class AIClient:

    def __init__(self, **kwargs):
        raise NotImplementedError("This class should be subclassed and initialized with the appropriate parameters.")   

    @abstractmethod
    def chat(self, model: str, messages: list[dict[str, str]]) -> dict:
        raise NotImplementedError("This method should be implemented by subclasses.")