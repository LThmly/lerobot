#!/usr/bin/env python

# Copyright 2026 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from lerobot.motors import CustomRegister
from lerobot.motors.motors_bus import Motor, MotorNormMode
from tests.mocks.mock_motors_bus import MockMotorsBus

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTER_MODULE = REPO_ROOT / "src" / "lerobot" / "motors" / "registers.py"
GENERATOR = REPO_ROOT / "scripts" / "generate_motor_registers.py"
TYPE_CHECK_SNIPPET = """
from lerobot.motors import CustomRegister, SerialMotorsBus

def check(bus: SerialMotorsBus, name: str) -> None:
    bus.read("Present_Position", "joint")
    bus.read("present_position", "joint")
    bus.read("PRESENT_POSITION", "joint")
    bus.write("Goal_Position", "joint", 1)
    bus.sync_read("Present_Position")
    bus.sync_write("Goal_Position", {"joint": 1})
    bus.read(CustomRegister(name), "joint")
    bus.read("Present_Positon", "joint")
    bus.write("Goal_Poziton", "joint", 1)
    bus.sync_read("Present_Positionn")
    bus.sync_write("Goal_Pozition", {"joint": 1})
"""
TYPOS = ("Present_Positon", "Goal_Poziton", "Present_Positionn", "Goal_Pozition")


@pytest.fixture(scope="session")
def mypy_report(tmp_path_factory: pytest.TempPathFactory) -> str:
    mypy_api = pytest.importorskip("mypy.api")
    snippet = tmp_path_factory.mktemp("register-types") / "check.py"
    snippet.write_text(TYPE_CHECK_SNIPPET)
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("MYPYPATH", str(REPO_ROOT / "src"))
        report, errors, _ = mypy_api.run(
            [
                str(snippet),
                "--cache-dir",
                str(tmp_path_factory.mktemp("mypy-cache")),
                "--follow-imports=silent",
            ]
        )
    assert not errors, errors
    return report


def test_mypy_rejects_register_typos_on_every_serial_access(mypy_report: str) -> None:
    arg_errors = [line for line in mypy_report.splitlines() if "arg-type" in line]
    assert len(arg_errors) == len(TYPOS), mypy_report
    for typo in TYPOS:
        assert any(typo in line for line in arg_errors), f"{typo!r} was not rejected:\n{mypy_report}"


def test_generated_names_match_rustypot() -> None:
    pytest.importorskip("rustypot")
    spec = importlib.util.spec_from_file_location("generate_motor_registers", GENERATOR)
    assert spec is not None and spec.loader is not None
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)

    expected = generator.render_module(generator.collect_register_names())
    assert REGISTER_MODULE.read_text() == expected


def test_custom_register_is_passed_through_to_rustypot() -> None:
    bus = MockMotorsBus("/dev/dummy-port", {"joint": Motor(1, "model_1", MotorNormMode.RANGE_M100_100)})
    bus.connect(handshake=False)
    bus._bus.seed(1, "model_number", 5678)

    assert bus.read(CustomRegister("MODEL_NUMBER"), "joint") == 5678
    assert bus._bus.reads == [(1, "model_number")]
