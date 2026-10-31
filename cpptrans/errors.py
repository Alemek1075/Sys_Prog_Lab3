class CompileError(Exception):
    def __init__(self, message, line=None, col=None, stage='syntax'):
        super().__init__(message)
        self.message = message
        self.line = line
        self.col = col
        self.stage = stage

    def __str__(self):
        where = f"рядок {self.line}" if self.line else ""
        if self.line and self.col:
            where += f", позиція {self.col}"
        return f"{where}: {self.message}" if where else self.message

    def to_dict(self):
        return {'stage': self.stage, 'message': self.message, 'line': self.line, 'col': self.col}


class RuntimeFault(Exception):
    def __init__(self, message, line=None):
        super().__init__(message)
        self.message = message
        self.line = line

    def __str__(self):
        return f"рядок {self.line}: {self.message}" if self.line else self.message
