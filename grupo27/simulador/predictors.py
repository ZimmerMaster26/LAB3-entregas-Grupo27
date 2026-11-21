"""Extensible branch predictors used by pipelined execution."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BranchPredictor(ABC):
    """Predicts a conditional branch as taken or not taken."""

    @abstractmethod
    def predict(self, address: int) -> bool:
        raise NotImplementedError

    def update(self, address: int, taken: bool) -> None:
        """Update predictor state after the branch is resolved."""


class NeverTakenPredictor(BranchPredictor):
    def predict(self, address: int) -> bool:
        return False


class AlwaysTakenPredictor(BranchPredictor):
    def predict(self, address: int) -> bool:
        return True


class OneBitPredictor(BranchPredictor):
    def __init__(self):
        self._state: dict[int, bool] = {}

    def predict(self, address: int) -> bool:
        return self._state.get(address, False)

    def update(self, address: int, taken: bool) -> None:
        self._state[address] = bool(taken)


class TwoBitPredictor(BranchPredictor):
    """Per-address saturating counter; weakly not-taken on first encounter."""

    def __init__(self):
        self._state: dict[int, int] = {}

    def predict(self, address: int) -> bool:
        return self._state.get(address, 1) >= 2

    def update(self, address: int, taken: bool) -> None:
        counter = self._state.get(address, 1)
        self._state[address] = min(3, counter + 1) if taken else max(0, counter - 1)


PREDICTORS = {
    "never": NeverTakenPredictor,
    "always": AlwaysTakenPredictor,
    "1bit": OneBitPredictor,
    "2bit": TwoBitPredictor,
}


def create_predictor(name: str | BranchPredictor) -> BranchPredictor:
    if isinstance(name, BranchPredictor):
        return name
    try:
        return PREDICTORS[name.lower()]()
    except KeyError as error:
        supported = ", ".join(PREDICTORS)
        raise ValueError(f"predictor desconocido: {name}; use {supported}") from error

