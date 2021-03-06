from labby.cli.core import BaseArgumentParser, Command


class HelloCommand(Command[BaseArgumentParser]):
    TRIGGER: str = "hello"

    def main(self, args: BaseArgumentParser) -> int:
        print(self.get_client().hello())
        return 0
