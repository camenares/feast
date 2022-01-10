from dataclasses import dataclass
from typing import Any, Iterable, List, Tuple, TypeVar

from feast.diff.property_diff import PropertyDiff, TransitionType
from feast.infra.infra_object import (
    DATASTORE_INFRA_OBJECT_CLASS_TYPE,
    DYNAMODB_INFRA_OBJECT_CLASS_TYPE,
    SQLITE_INFRA_OBJECT_CLASS_TYPE,
    InfraObject,
)
from feast.protos.feast.core.DatastoreTable_pb2 import (
    DatastoreTable as DatastoreTableProto,
)
from feast.protos.feast.core.DynamoDBTable_pb2 import (
    DynamoDBTable as DynamoDBTableProto,
)
from feast.protos.feast.core.InfraObject_pb2 import Infra as InfraProto
from feast.protos.feast.core.SqliteTable_pb2 import SqliteTable as SqliteTableProto


@dataclass
class InfraObjectDiff:
    name: str
    infra_object_type: str
    current_infra_object: Any
    new_infra_object: Any
    infra_object_property_diffs: List[PropertyDiff]
    transition_type: TransitionType


@dataclass
class InfraDiff:
    infra_object_diffs: List[InfraObjectDiff]

    def __init__(self):
        self.infra_object_diffs = []

    def update(self):
        pass

    def to_string(self):
        pass


U = TypeVar("U", DatastoreTableProto, DynamoDBTableProto, SqliteTableProto)


def tag_infra_proto_objects_for_keep_delete_add(
    existing_objs: Iterable[U], desired_objs: Iterable[U]
) -> Tuple[Iterable[U], Iterable[U], Iterable[U]]:
    existing_obj_names = {e.name for e in existing_objs}
    desired_obj_names = {e.name for e in desired_objs}

    objs_to_add = [e for e in desired_objs if e.name not in existing_obj_names]
    objs_to_keep = [e for e in desired_objs if e.name in existing_obj_names]
    objs_to_delete = [e for e in existing_objs if e.name not in desired_obj_names]

    return objs_to_keep, objs_to_delete, objs_to_add


def diff_infra_protos(
    current_infra_proto: InfraProto, new_infra_proto: InfraProto
) -> InfraDiff:
    infra_diff = InfraDiff()

    infra_object_class_types_to_str = {
        DATASTORE_INFRA_OBJECT_CLASS_TYPE: "datastore table",
        DYNAMODB_INFRA_OBJECT_CLASS_TYPE: "dynamodb table",
        SQLITE_INFRA_OBJECT_CLASS_TYPE: "sqlite table",
    }

    for infra_object_class_type in infra_object_class_types_to_str:
        current_infra_objects = get_infra_object_protos_by_type(
            current_infra_proto, infra_object_class_type
        )
        new_infra_objects = get_infra_object_protos_by_type(
            new_infra_proto, infra_object_class_type
        )
        (
            infra_objects_to_keep,
            infra_objects_to_delete,
            infra_objects_to_add,
        ) = tag_infra_proto_objects_for_keep_delete_add(
            current_infra_objects, new_infra_objects,
        )

        for e in infra_objects_to_add:
            infra_diff.infra_object_diffs.append(
                InfraObjectDiff(
                    e.name,
                    infra_object_class_types_to_str[infra_object_class_type],
                    None,
                    e,
                    [],
                    TransitionType.CREATE,
                )
            )
        for e in infra_objects_to_delete:
            infra_diff.infra_object_diffs.append(
                InfraObjectDiff(
                    e.name,
                    infra_object_class_types_to_str[infra_object_class_type],
                    e,
                    None,
                    [],
                    TransitionType.DELETE,
                )
            )
        for e in infra_objects_to_keep:
            current_infra_object = [
                _e for _e in current_infra_objects if _e.name == e.name
            ][0]
            infra_diff.infra_object_diffs.append(
                diff_between(
                    current_infra_object,
                    e,
                    infra_object_class_types_to_str[infra_object_class_type],
                )
            )

    return infra_diff


def get_infra_object_protos_by_type(
    infra_proto: InfraProto, infra_object_class_type: str
) -> List[U]:
    return [
        InfraObject.from_infra_object_proto(infra_object).to_proto()
        for infra_object in infra_proto.infra_objects
        if infra_object.infra_object_class_type == infra_object_class_type
    ]


FIELDS_TO_IGNORE = {"project"}


def diff_between(current: U, new: U, infra_object_type: str) -> InfraObjectDiff:
    assert current.DESCRIPTOR.full_name == new.DESCRIPTOR.full_name
    property_diffs = []
    transition: TransitionType = TransitionType.UNCHANGED
    if current != new:
        for _field in current.DESCRIPTOR.fields:
            if _field.name in FIELDS_TO_IGNORE:
                continue
            if getattr(current, _field.name) != getattr(new, _field.name):
                transition = TransitionType.UPDATE
                property_diffs.append(
                    PropertyDiff(
                        _field.name,
                        getattr(current, _field.name),
                        getattr(new, _field.name),
                    )
                )
    return InfraObjectDiff(
        new.name, infra_object_type, current, new, property_diffs, transition,
    )
