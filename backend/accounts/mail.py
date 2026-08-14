from django.core.mail.backends.console import EmailBackend as DjangoConsoleEmailBackend


class ReadableConsoleEmailBackend(DjangoConsoleEmailBackend):
    """Print development email bodies without MIME transfer encoding."""

    def write_message(self, message):
        self.stream.write(f"Subject: {message.subject}\n")
        self.stream.write(f"From: {message.from_email}\n")
        self.stream.write(f"To: {', '.join(message.to)}\n\n")
        self.stream.write(message.body)
        if not message.body.endswith("\n"):
            self.stream.write("\n")
        self.stream.write("-" * 79)
        self.stream.write("\n")
