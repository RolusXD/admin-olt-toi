from abc import ABC, abstractmethod


class DeviceDriver(ABC):
    @abstractmethod
    def connect(self, disable_paging: bool = True) -> None:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def execute(self, command: str, read_only: bool = True) -> str:
        raise NotImplementedError

    @abstractmethod
    def backup(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        raise NotImplementedError
