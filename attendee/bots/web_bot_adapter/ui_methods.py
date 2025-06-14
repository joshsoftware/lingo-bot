class UiException(Exception):
    def __init__(self, message, step, inner_exception):
        self.step = step
        self.inner_exception = inner_exception
        super().__init__(message)


# When this exception is raised, the bot will stop running and log that it was denied access to the meeting
class UiRequestToJoinDeniedException(UiException):
    def __init__(self, message, step=None, inner_exception=None):
        super().__init__(message, step, inner_exception)


class UiRetryableException(UiException):
    def __init__(self, message, step=None, inner_exception=None):
        super().__init__(message, step, inner_exception)


class UiCouldNotLocateElementException(UiRetryableException):
    def __init__(self, message, step=None, inner_exception=None):
        super().__init__(message, step, inner_exception)


class UiCouldNotClickElementException(UiRetryableException):
    def __init__(self, message, step=None, inner_exception=None):
        super().__init__(message, step, inner_exception)
