# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.
"""Tools for serializing and deserializing material descriptions."""
import io
import logging
import struct

from .deserialize import decode_value, unpack_value
from .serialize import encode_value
from dynamodb_encryption_sdk.exceptions import InvalidMaterialsetError, InvalidMaterialsetVersionError
from dynamodb_encryption_sdk.internal.defaults import LOGGING_NAME, MATERIAL_DESCRIPTION_VERSION
from dynamodb_encryption_sdk.internal.identifiers import Tag
from dynamodb_encryption_sdk.internal.str_ops import to_bytes, to_str

__all__ = ('serialize', 'deserialize')
_LOGGER = logging.getLogger(LOGGING_NAME)


def serialize(material_description):
    # type: (Dict[Text, Text]) -> dynamodb_types.BINARY_ATTRIBUTE
    """Serialize a material description dictionary into a DynamodDB attribute.

    :param dict material_description: Material description dictionary
    :returns: Serialized material description as a DynamoDB binary attribute value
    :rtype: dict
    """
    material_description_bytes = bytearray(MATERIAL_DESCRIPTION_VERSION)

    # TODO: verify Java sorting order
    for name, value in sorted(material_description.items(), key=lambda x: x[0]):
        try:
            material_description_bytes.extend(encode_value(to_bytes(name)))
            material_description_bytes.extend(encode_value(to_bytes(value)))
        except (TypeError, struct.error):
            raise InvalidMaterialsetError('Invalid name or value in material description: "{name}"="{value}"'.format(
                name=name,
                value=value
            ))

    return {Tag.BINARY.dynamodb_tag: bytes(material_description_bytes)}


def deserialize(serialized_material_description):
    # type: (dynamodb_types.BINARY_ATTRIBUTE) -> Dict[Text, Text]
    """Deserialize a serialized material description attribute into a material description dictionary.

    :param dict serialized_material_description: DynamoDB attribute value containing serialized material description.
    :returns: Material description dictionary
    :rtype: dict
    :raises InvalidMaterialsetError: if material description is invalid or malformed
    """
    try:
        _raw_material_description = serialized_material_description[Tag.BINARY.dynamodb_tag]

        material_description_bytes = io.BytesIO(_raw_material_description)
        total_bytes = len(_raw_material_description)
    except (TypeError, KeyError):
        message = 'Invalid material description'
        _LOGGER.exception(message)
        raise InvalidMaterialsetError(message)
    # We don't currently do anything with the version, but do check to make sure it is the one we know about.
    _read_version(material_description_bytes)

    material_description = {}
    try:
        while material_description_bytes.tell() < total_bytes:
            name = to_str(decode_value(material_description_bytes))
            value = to_str(decode_value(material_description_bytes))
            material_description[name] = value
    except struct.error:
        message = 'Invalid material description'
        _LOGGER.exception(message)
        raise InvalidMaterialsetError(message)
    return material_description


def _read_version(material_description_bytes):
    # type: (io.BytesIO) -> None
    """Read the version from the serialized material description and raise an error if it is unknown.

    :param material_description_bytes: serializezd material description
    :type material_description_bytes: io.BytesIO
    :raises InvalidMaterialsetError: if malformed version
    :raises InvalidMaterialsetVersionError: if unknown version is found
    """
    try:
        (version,) = unpack_value('>4s', material_description_bytes)
    except struct.error:
        message = 'Malformed material description version'
        _LOGGER.exception(message)
        raise InvalidMaterialsetError(message)
    if version != MATERIAL_DESCRIPTION_VERSION:
        raise InvalidMaterialsetVersionError('Invalid material description version: {}'.format(repr(version)))