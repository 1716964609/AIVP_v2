class AIVPError(RuntimeError):
    pass


class BudgetExceeded(AIVPError):
    pass


class CommandFailed(AIVPError):
    def __init__(
        self,
        message: str,
        returncode: int = 1,
    ):
        super().__init__(message)
        self.returncode = returncode


class StateIntegrityError(AIVPError):
    pass



class InjectedCrash(AIVPError):
    """Intentional crash used for durable-execution fault injection."""
    pass


class PolicyDenied(AIVPError):
    pass


class HumanApprovalRequired(AIVPError):
    pass
