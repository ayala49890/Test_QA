from socket import socket, AF_INET, SOCK_STREAM

CONNECTION_TIMEOUT_SECONDS = 5


class AmmeterCommunicationError(Exception):
    """Raised when a server connection, request, or response is invalid."""


def request_current_from_ammeter(port: int, command: bytes) -> float:
    """Send `command` to the ammeter server on `port` and return the parsed current in Amps."""
    try:
        with socket(AF_INET, SOCK_STREAM) as s:
            s.settimeout(CONNECTION_TIMEOUT_SECONDS)
            s.connect(('localhost', port))
            s.sendall(command)
            data = s.recv(1024)
    except OSError as exc:
        raise AmmeterCommunicationError(f"Could not reach ammeter server on port {port}: {exc}") from exc

    if not data:
        raise AmmeterCommunicationError(
            f"No data received from port {port} - the server did not recognize the command {command!r}."
        )

    try:
        return float(data.decode('utf-8'))
    except ValueError as exc:
        raise AmmeterCommunicationError(f"Port {port} returned a non-numeric response: {data!r}") from exc

