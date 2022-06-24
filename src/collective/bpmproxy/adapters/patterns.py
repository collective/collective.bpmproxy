class PatternsSettings(object):
    def __init__(self, context, request, field):
        self.request = request
        self.context = context
        self.field = field

    def __call__(self):
        return {
            # 'data-pat-code-editor': 'language: json; theme: tomorrow;',
            "data-pat-code-editor": "language: js; theme: tomorrow;",
        }
