class VocabItem:
    """A token/value pair yielded while building a vocabulary."""

    def __init__(self, token, value):
        self.token = token
        self.value = value
