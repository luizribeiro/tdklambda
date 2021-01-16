import copy
import os
import sys
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import (
    Dict,
    Generic,
    Optional,
    Type,
    TypeVar,
    Union,
    cast,
)

from mashumaro import DataClassMessagePackMixin
from mashumaro.serializer.msgpack import EncodedData
from pynng import Rep0

from labby.config import Config
from labby.experiment.runner import ExperimentSequenceStatus
from labby.server.logging import logger
from labby.utils.typing import get_args


DEFAULT_ADDRESS = "tcp://127.0.0.1:14337"


@dataclass(frozen=True)
class ServerInfo:
    address: str
    existing: bool
    pid: int


@dataclass(frozen=True)
class ServerResponseComponent(DataClassMessagePackMixin, ABC):
    pass


ServerResponse = ServerResponseComponent


TResponse = TypeVar("TResponse", bound=Union[None, ServerResponse])
TNonOptionalResponse = TypeVar("TResponse", bound=ServerResponse)
_ALL_REQUEST_TYPES: Dict[str, Type["ServerRequest[ServerResponse]"]] = {}


@dataclass(frozen=True)
class ServerRequest(Generic[TResponse], DataClassMessagePackMixin, ABC):
    def __init_subclass__(cls: Type[object]) -> None:
        subclass = cast(Type["ServerRequest[ServerResponse]"], cls)
        _ALL_REQUEST_TYPES[subclass.__name__] = subclass
        super().__init_subclass__()

    def get_response_type(cls) -> TResponse:
        # pyre-ignore[16]: pyre does not understand __orig_bases__
        return get_args(cls.__orig_bases__[0])[0]

    @classmethod
    def handle_from_msgpack(
        cls, server: "Server", msg: EncodedData
    ) -> Optional[EncodedData]:
        (request_type, msg) = cast(bytes, msg).split(b":", 1)
        logger.info(f"Received request {request_type.decode()}")
        klass = _ALL_REQUEST_TYPES[request_type.decode()]
        request = klass.from_msgpack(msg)
        response = request.handle(server)
        logger.debug(f"Prepared response of type {type(response).__name__}")
        if response is None:
            return None
        return response.to_msgpack()

    @abstractmethod
    def handle(self, server: "Server") -> TResponse:
        raise NotImplementedError


class Server:
    config: Config
    _experiment_sequence_status_lock: threading.Lock
    _experiment_sequence_status: Optional[ExperimentSequenceStatus]

    def __init__(self, config: Config) -> None:
        self.config = config
        self._experiment_sequence_status = None
        self._experiment_sequence_status_lock = threading.Lock()

    def start(self) -> ServerInfo:
        address = DEFAULT_ADDRESS

        existing_pid = self.get_existing_pid()
        if existing_pid:
            return ServerInfo(address=address, existing=True, pid=existing_pid)

        child_pid = os.fork()
        if child_pid != 0:
            logger.info(f"Started server (pid: {child_pid}) on address {address}")
            self._create_pid_file(child_pid)
            return ServerInfo(address=address, existing=False, pid=child_pid)

        with Rep0(listen=address) as rep:
            self._run(rep)

        sys.exit(0)

    def stop(self) -> None:
        logger.info(f"Stopping server (pid: {os.getpid()})")
        sys.exit(0)

    @classmethod
    def get_existing_pid(cls) -> Optional[int]:
        try:
            with open(".labby/pid", "r") as pid_file:
                return int(pid_file.read())
        except (FileNotFoundError, ValueError):
            return None

    def _create_pid_file(cls, pid: int) -> Optional[int]:
        os.makedirs(".labby", exist_ok=True)
        with open(".labby/pid", "w") as pid_file:
            pid_file.write(str(pid))

    def _delete_pid_file(self) -> None:
        try:
            os.remove(".labby/pid")
        except OSError:
            pass

    def set_experiment_sequence_status(
        self,
        experiment_sequence_status: ExperimentSequenceStatus,
    ) -> None:
        with self._experiment_sequence_status_lock:
            self._experiment_sequence_status = copy.deepcopy(experiment_sequence_status)

    def get_experiment_sequence_status(self) -> Optional[ExperimentSequenceStatus]:
        with self._experiment_sequence_status_lock:
            return copy.deepcopy(self._experiment_sequence_status)

    def _run(self, socket: Rep0) -> None:
        try:
            while True:
                logger.info("Waiting for requests...")
                message = socket.recv()
                response = ServerRequest.handle_from_msgpack(self, message)
                if response is not None:
                    logger.debug("Sending response back to client")
                    socket.send(response)
                    logger.debug("Sent response")
        finally:
            self._delete_pid_file()
