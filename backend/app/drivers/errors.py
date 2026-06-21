class DriverError(RuntimeError):
    """Base error for device driver failures."""


class DriverTimeoutError(DriverError):
    """Timeout while waiting for CLI interaction.

    Optionally carries a sanitized excerpt of the last CLI output so that
    callers can log or expose it in diagnostic mode without re-reading from
    the transport.
    """

    def __init__(self, message: str, output: str | None = None):
        super().__init__(message)
        # Sanitized CLI output excerpt, may be None when not provided
        self.output = output


class DriverCommandError(DriverError):
    def __init__(self, command: str, message: str, output: str):
        super().__init__(f"{message}: {command}")
        self.command = command
        self.message = message
        self.output = output
