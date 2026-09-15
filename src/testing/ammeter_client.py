from Ammeters.Circutor_Ammeter import CircutorAmmeter
from Ammeters.Entes_Ammeter import EntesAmmeter
from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from Ammeters.client import request_current_from_ammeter

# Registry mapping a config-friendly ammeter type name to its emulator class.
# The class itself still owns the wire-protocol command (get_current_command),
# so this mapping never duplicates that detail.
AMMETER_CLASSES = {
    "greenlee": GreenleeAmmeter,
    "entes": EntesAmmeter,
    "circutor": CircutorAmmeter,
}


class UnknownAmmeterTypeError(Exception):
    """Raised when an ammeter type is not in AMMETER_CLASSES."""


class AmmeterClient:
    """Unified client API: measure() works the same way for every ammeter type."""

    def __init__(self, ammeters_config: dict):
        """`ammeters_config` is the 'ammeters' section of config.yaml: {type: {port: int}}."""
        self._ports_by_type = {name: settings["port"] for name, settings in ammeters_config.items()}

    def measure(self, ammeter_type: str) -> float:
        """Take a single current measurement (in Amps) from the given ammeter type."""
        if ammeter_type not in AMMETER_CLASSES:
            raise UnknownAmmeterTypeError(
                f"Unknown ammeter type '{ammeter_type}'. Known types: {sorted(AMMETER_CLASSES)}"
            )
        if ammeter_type not in self._ports_by_type:
            raise UnknownAmmeterTypeError(
                f"Ammeter type '{ammeter_type}' has no port configured in config.yaml"
            )

        ammeter_class = AMMETER_CLASSES[ammeter_type]
        port = self._ports_by_type[ammeter_type]
        ammeter = ammeter_class(port)
        return request_current_from_ammeter(ammeter.port, ammeter.get_current_command)
