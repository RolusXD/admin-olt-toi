class DriverError(RuntimeError):
    pass


class DriverTimeoutError(DriverError):
    pass


class DriverCommandError(DriverError):
    def __init__(self, command: str, message: str, output: str):
        super().__init__(f"{message}: {command}")
        self.command = command
        self.message = message
        self.output = output
