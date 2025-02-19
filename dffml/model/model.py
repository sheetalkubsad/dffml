# SPDX-License-Identifier: MIT
# Copyright (c) 2019 Intel Corporation
"""
Model subclasses are responsible for training themselves on records, making
predictions about the value of a feature in the record, and assessing their
prediction accuracy.
"""
import abc
import json
import pathlib
from typing import AsyncIterator, Optional

from ..base import (
    config,
    BaseDataFlowFacilitatorObjectContext,
    BaseDataFlowFacilitatorObject,
)
from ..record import Record
from ..feature import Features
from .accuracy import Accuracy
from ..util.entrypoint import base_entry_point
from ..util.os import MODE_BITS_SECURE
from ..source.source import Sources, SourcesContext


class ModelNotTrained(Exception):
    pass


@config
class ModelConfig:
    location: str
    features: Features


class ModelContext(abc.ABC, BaseDataFlowFacilitatorObjectContext):
    """
    Abstract base class which should be derived from and implemented using
    various machine learning frameworks or concepts.
    """

    def __init__(self, parent: "Model") -> None:
        self.parent = parent

    @abc.abstractmethod
    async def train(self, sources: Sources):
        """
        Train using records as the data to learn from.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    async def predict(self, sources: SourcesContext) -> AsyncIterator[Record]:
        """
        Uses trained data to make a prediction about the quality of a record.
        """
        raise NotImplementedError()
        yield (Record(""), "", 0.0)  # skipcq: PYL-W0101


@base_entry_point("dffml.model", "model")
class Model(BaseDataFlowFacilitatorObject):
    """
    Abstract base class which should be derived from and implemented using
    various machine learning frameworks or concepts.
    """

    CONFIG = ModelConfig

    def __init__(self, config):
        super().__init__(config)
        # TODO Just in case its a string. We should make it so that on
        # instantiation of an @config we convert properties to their correct
        # types.
        location = getattr(self.config, "location", None)
        if isinstance(location, str):
            location = pathlib.Path(location)
        if isinstance(location, pathlib.Path):
            # to treat "~" as the the home location rather than a literal
            location = location.expanduser().resolve()
            # TODO Change all model configs to make them support mutable
            # location config properties
            with self.config.no_enforce_immutable():
                self.config.location = location

    def __call__(self) -> ModelContext:
        self._make_config_location()
        return self.CONTEXT(self)

    def _make_config_location(self):
        """
        If the config object for this model contains the location property
        then create it if it does not exist.
        """
        location = getattr(self.config, "location", None)
        if location is not None:
            location = pathlib.Path(location)
            if not location.is_dir():
                location.mkdir(mode=MODE_BITS_SECURE, parents=True)


class SimpleModelNoContext:
    """
    No need for CONTEXT since we implement __call__
    """


class SimpleModel(Model):
    DTYPES = [int, float]
    NUM_SUPPORTED_FEATURES = -1
    SUPPORTED_LENGTHS = None
    CONTEXT = SimpleModelNoContext

    def __init__(self, config: "BaseConfig") -> None:
        super().__init__(config)
        self.storage = {}
        if hasattr(self.config, "features"):
            self.features = self.applicable_features(self.config.features)
        self._in_context = 0

    def __call__(self):
        return self

    async def __aenter__(self) -> Model:
        self._in_context += 1
        # If we've already entered the model's context once, don't reload
        if self._in_context > 1:
            return self
        self._make_config_location()
        self.open()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self._in_context -= 1
        if not self._in_context:
            self.close()

    @property
    def parent(self):
        """
        Simple models are both the parent and the context. This property is used
        to fake out anything attempting to access the model context's parent.
        """
        return self

    def open(self):
        """
        Load saved model from disk if it exists.
        """
        # Load saved data if this is the first time we've entred the model
        filepath = self.disk_path(extention=".json")
        if filepath.is_file():
            self.storage = json.loads(filepath.read_text())
            self.logger.debug("Loaded model from %s", filepath)
        else:
            self.logger.debug("No saved model in %s", filepath)

    def close(self):
        """
        Save model to disk.
        """
        filepath = self.disk_path(extention=".json")
        filepath.write_text(json.dumps(self.storage))
        self.logger.debug("Saved model to %s", filepath)

    def disk_path(self, extention: Optional[str] = None):
        """
        We do this for convenience of the user so they can usually just use the
        default location and if they train models with different parameters
        this method transparently to the user creates a filename unique the that
        configuration of the model where data is saved and loaded.
        """
        # Export the config to a dictionary
        exported = self.config._asdict()
        # Remove the location from the exported dict
        if "location" in exported:
            del exported["location"]
        # Replace features with the sorted list of features
        if "features" in exported:
            exported["features"] = dict(sorted(exported["features"].items()))
        # Hash the exported config
        return pathlib.Path(self.config.location, "Model")

    def applicable_features(self, features):
        usable = []
        # Check that we aren't trying to use more features than the model
        # supports
        if (
            self.NUM_SUPPORTED_FEATURES != -1
            and len(features) != self.NUM_SUPPORTED_FEATURES
        ):
            msg = f"{self.__class__.__qualname__} doesn't support more than "
            if self.NUM_SUPPORTED_FEATURES == 1:
                msg += f"{self.NUM_SUPPORTED_FEATURES} feature"
            else:
                msg += f"{self.NUM_SUPPORTED_FEATURES} features"
            raise ValueError(msg)
        # Check data type and length for each feature
        for feature in features:
            if self.check_applicable_feature(feature):
                usable.append(feature.name)
        # Return a sorted list of feature names for consistency. In case users
        # provide the same list of features to applicable_features in a
        # different order.
        return sorted(usable)

    def check_applicable_feature(self, feature):
        # Check the data datatype is in the list of supported data types
        self.check_feature_dtype(feature.dtype)
        # Check that length (dimensions) of feature is supported
        self.check_feature_length(feature.length)
        return True

    def check_feature_dtype(self, dtype):
        if dtype not in self.DTYPES:
            msg = f"{self.__class__.__qualname__} only supports features "
            msg += f"with these data types: {self.DTYPES}"
            raise ValueError(msg)

    def check_feature_length(self, length):
        # If SUPPORTED_LENGTHS is None then all lengths are supported
        if self.SUPPORTED_LENGTHS and length not in self.SUPPORTED_LENGTHS:
            msg = f"{self.__class__.__qualname__} only supports "
            msg += f"{self.SUPPORTED_LENGTHS} dimensional values"
            raise ValueError(msg)
