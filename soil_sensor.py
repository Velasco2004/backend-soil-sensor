"""Receive soil readings forwarded by the Pi-connected T3S3 LoRa board.

The receiver expects one newline-terminated JSON object per radio message.
"""

from dataclasses import asdict, dataclass
import json
from typing import Any, Iterator


@dataclass(frozen=True)
class SoilReading:
    """A decoded reading sent by the remote sensor-side T3S3."""

    moisture_percent: float
    temperature_c: float
    ec_us_cm: int
    ph: float
    nitrogen_mg_kg: int
    phosphorus_mg_kg: int
    potassium_mg_kg: int
    salinity_mg_l: int

    def to_dict(self) -> dict[str, float | int]:
        """Return the reading in a JSON-serializable form."""
        return asdict(self)


class SoilSensor:
    """Receive soil measurements from the local T3S3 over USB serial.

    Each line from the receiver must be a UTF-8 JSON object containing
    ``moisture_percent``, ``temperature_c``, ``ec_us_cm``, ``ph``,
    ``nitrogen_mg_kg``, ``phosphorus_mg_kg``, ``potassium_mg_kg``, and
    ``salinity_mg_l``. The remote T3S3 reads the sensor and transmits this
    payload over LoRa; this class never communicates with the sensor directly.
    """

    def __init__(
        self,
        port: str = "/dev/ttyACM0",
        baudrate: int = 115200,
        timeout: float = 2.0,
    ) -> None:
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout

    def read(self) -> SoilReading:
        """Receive one JSON line from the Pi-connected LoRa board.

        For continuous monitoring, use :meth:`iter_readings` so the serial
        connection remains open between messages.
        """
        import serial

        with serial.Serial(self.port, self.baudrate, timeout=self.timeout) as connection:
            line = connection.readline()
            if not line:
                raise TimeoutError(
                    f"No LoRa message received on {self.port} within {self.timeout} seconds"
                )
            return self._decode_line(line)

    def iter_readings(self) -> Iterator[SoilReading]:
        """Yield readings continuously while keeping the serial port open."""
        import serial

        with serial.Serial(self.port, self.baudrate, timeout=self.timeout) as connection:
            while True:
                line = connection.readline()
                if not line:
                    continue
                yield self._decode_line(line)

    @staticmethod
    def _decode_line(line: bytes) -> SoilReading:
        try:
            payload: Any = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Received invalid UTF-8 JSON from the LoRa receiver") from error

        if not isinstance(payload, dict):
            raise ValueError("LoRa message must be a JSON object")

        required_fields = {
            "moisture_percent": float,
            "temperature_c": float,
            "ec_us_cm": int,
            "ph": float,
            "nitrogen_mg_kg": int,
            "phosphorus_mg_kg": int,
            "potassium_mg_kg": int,
            "salinity_mg_l": int,
        }
        values: dict[str, float | int] = {}
        for name, expected_type in required_fields.items():
            value = payload.get(name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"LoRa message field {name!r} must be numeric")
            if expected_type is int and not isinstance(value, int):
                raise ValueError(f"LoRa message field {name!r} must be an integer")
            values[name] = value

        return SoilReading(**values)
