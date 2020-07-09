import dataclasses
from decimal import Decimal
from pathlib import Path
import os
import subprocess
import re
import tempfile
from typing import Union, NamedTuple, Tuple
from typing_extensions import Literal


PolarizationType = Union[Literal[0], Literal[1]]
RadioClimateType = Union[
    Literal[1],
    Literal[2],
    Literal[3],
    Literal[4],
    Literal[5],
    Literal[6],
    Literal[7],
    Literal[8],
    Literal[9],
]
FreeSpacePathLossDecibels = Decimal
IWOTMPathLossDecibels = Decimal
FieldStrengthDBuV = Decimal


class SplatReportException(Exception):
    def __init__(self, *args, **kw):
        self.report_text = kw.pop("report_text", None)
        super().__init__(*args, **kw)


class LRPFields(NamedTuple):
    erp_W: Decimal
    frequency_MHz: Decimal
    polarization: PolarizationType
    radio_climate: RadioClimateType
    earth_dielectric_constant: Decimal = Decimal("15.000")
    earth_conductivity: Decimal = Decimal("0.005")
    atmospheric_bending_constant: Decimal = Decimal("301.000")
    fraction_situations: Decimal = Decimal("0.50")
    fraction_time: Decimal = Decimal("0.50")


class QTHFields(NamedTuple):
    name: str
    latitude: Decimal
    longitude_EtoW: Decimal
    height_m: Decimal


@dataclasses.dataclass
class Transmitter:
    name: str
    latitude: Decimal
    longitude_WtoE: Decimal
    height_m: Decimal
    eirp_W: Decimal
    frequency_MHz: Decimal
    polarization: PolarizationType
    # Could be moved to a `Fresnel` class that specifies data about the environment:
    radio_climate: RadioClimateType

    def __post_init__(self):
        def _convert_to_decimal(val):
            if isinstance(val, Decimal):
                return val
            if isinstance(val, float):
                return Decimal(str(val))
            return Decimal(val)

        for field in dataclasses.fields(self):
            if field.type is Decimal:
                setattr(
                    self, field.name, _convert_to_decimal(getattr(self, field.name))
                )

    def to_qthfields(self) -> QTHFields:
        return QTHFields(
            name=self.name,
            latitude=self.latitude,
            longitude_EtoW=(Decimal("360") - self.longitude_WtoE) % 360,
            height_m=self.height_m,
        )

    def to_lrpfields(self) -> LRPFields:
        return LRPFields(
            erp_W=self.eirp_W / Decimal("1.64"),
            frequency_MHz=self.frequency_MHz,
            polarization=self.polarization,
            radio_climate=self.radio_climate,
        )


@dataclasses.dataclass
class Receiver:
    name: str
    latitude: Decimal
    longitude_WtoE: Decimal
    height_m: Decimal

    def __post_init__(self):
        def _convert_to_decimal(val):
            if isinstance(val, Decimal):
                return val
            if isinstance(val, float):
                return Decimal(str(val))
            return Decimal(val)

        for field in dataclasses.fields(self):
            if field.type is Decimal:
                setattr(
                    self, field.name, _convert_to_decimal(getattr(self, field.name))
                )

    def to_qthfields(self) -> QTHFields:
        return QTHFields(
            name=self.name,
            latitude=self.latitude,
            longitude_EtoW=(Decimal("360") - self.longitude_WtoE) % 360,
            height_m=self.height_m,
        )


QTH_TEMPLATE = "\n".join(
    ["{name}", "{latitude}", "{longitude_EtoW}", "{height_m} meters"]
)

LRP_TEMPLATE = "\n".join(
    [
        "{earth_dielectric_constant}	; Earth Dielectric Constant (Relative permittivity)",
        "{earth_conductivity}; Earth Conductivity (Siemens per meter)",
        "{atmospheric_bending_constant}	; Atmospheric Bending Constant (N-Units)",
        "{frequency_MHz}	; Frequency in MHz (20 MHz to 20 GHz)",
        "{radio_climate}	; Radio Climate",
        "{polarization}	; Polarization (0 = Horizontal, 1 = Vertical)",
        "{fraction_situations}	; Fraction of Situations",
        "{fraction_time}	; Fraction of Time",
        "{erp_W} ; ERP",
    ]
)

REPORT_FILENAME_TEMPLATE = "{transmitter.name}-to-{receiver.name}.txt"


def splat_report_values(
    terrain_folder: str,
    cities_filepath: str,
    transmitter: Transmitter,
    receiver: Receiver,
    timeout=2,
) -> Tuple[FreeSpacePathLossDecibels, IWOTMPathLossDecibels, FieldStrengthDBuV]:
    """
    :raise: TimeoutExpired in case the subprocess takes too long
    :raise: SplatReportException in case the Splat report doesn't look as expected
    """
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmpdir_path = Path(tmpdirname)
        transmitter_qth_path = tmpdir_path / f"transmitter-{transmitter.name}.qth"
        transmitter_lrp_path = tmpdir_path / f"transmitter-{transmitter.name}.lrp"
        receiver_qth_path = tmpdir_path / f"receiver-{receiver.name}.qth"

        with transmitter_qth_path.open(
            "w"
        ) as transmitter_qth_file, transmitter_lrp_path.open(
            "w"
        ) as transmitter_lrp_file, receiver_qth_path.open(
            "w"
        ) as receiver_qth_file:
            transmitter_qth_file.write(
                QTH_TEMPLATE.format(**transmitter.to_qthfields()._asdict())
            )
            transmitter_lrp_file.write(
                LRP_TEMPLATE.format(**transmitter.to_lrpfields()._asdict())
            )
            receiver_qth_file.write(
                QTH_TEMPLATE.format(**receiver.to_qthfields()._asdict())
            )

        args = [
            "splat",
            "-metric",
            "-s",
            f"{cities_filepath}",
            "-d",
            f"{terrain_folder}",
            "-t",
            str(transmitter_qth_path),
            "-r",
            str(receiver_qth_path),
        ]
        subprocess.run(
            args,
            cwd=str(tmpdir_path),
            capture_output=True,
            universal_newlines=True,
            check=True,
            timeout=timeout,
        )

        output_path = tmpdir_path / REPORT_FILENAME_TEMPLATE.format(
            transmitter=transmitter, receiver=receiver
        )
        # Encoding copied from Splat gnuplot files:
        with open(str(output_path), encoding="iso_8859_1") as report_file:
            report_text = report_file.read()
            matches = re.search(
                r"Free space path loss: (\d*\.\d*) dB"
                r".*?"
                r"ITWOM Version 3.0 path loss: (\d*\.\d*) dB"
                r".*?"
                r"(\d*\.\d*) dBuV/meter",
                report_text,
                flags=re.DOTALL,
            )
            if matches:
                return (
                    Decimal(matches.group(1)),
                    Decimal(matches.group(2)),
                    Decimal(matches.group(3)),
                )

        raise SplatReportException(
            "Error reading splat report", report_text=report_text
        )


def test1():
    terrain_folder = os.environ["TERRAIN_FOLDER"]
    cities_filepath = os.environ["CITIES_FILEPATH"]
    transmitter = Transmitter(
        name="Menesble",
        latitude=Decimal("47.78194"),
        longitude_WtoE=Decimal("4.90917"),
        height_m=Decimal("41.0"),
        eirp_W=Decimal("80.0"),
        frequency_MHz=Decimal("800.00"),
        polarization=1,
        radio_climate=5,
    )
    receiver = Receiver(
        name="Bure",
        latitude=Decimal("47.738787"),
        longitude_WtoE=Decimal("4.8892801"),
        height_m=Decimal("2.0"),
    )
    assert splat_report_values(
        terrain_folder, cities_filepath, transmitter, receiver
    ) == [Decimal("104.55"), Decimal("141.82"), Decimal("42.53")]


if __name__ == "__main__":
    test1()
