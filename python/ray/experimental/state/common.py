import logging

from abc import ABC
from dataclasses import dataclass, fields
from typing import List, Dict, Union, Tuple, Set

from ray.dashboard.modules.job.common import JobInfo

logger = logging.getLogger(__name__)

DEFAULT_RPC_TIMEOUT = 30
DEFAULT_LIMIT = 1000


def filter_fields(data: dict, state_dataclass) -> dict:
    """Filter the given data using keys from a given state dataclass."""
    filtered_data = {}
    for field in fields(state_dataclass):
        if field.name in data:
            filtered_data[field.name] = data[field.name]
    return filtered_data


SupportedFilterType = Union[str, bool, int, float]


@dataclass(init=True)
class ListApiOptions:
    limit: int
    timeout: int
    filters: List[Tuple[str, SupportedFilterType]]
    # When the request is processed on the server side,
    # we should apply multiplier so that server side can finish
    # processing a request within timeout. Otherwise,
    # timeout will always lead Http timeout.
    _server_timeout_multiplier: float = 0.8

    # TODO(sang): Use Pydantic instead.
    def __post_init__(self):
        assert isinstance(self.limit, int)
        assert isinstance(self.timeout, int)
        # To return the data to users, when there's a partial failure
        # we need to have a timeout that's smaller than the users' timeout.
        # 80% is configured arbitrarily.
        self.timeout = int(self.timeout * self._server_timeout_multiplier)
        if self.filters is None:
            self.filters = []


class StateSchema(ABC):
    @classmethod
    def filterable_columns(cls) -> Set[str]:
        """Return a set of columns that support filtering.

        NOTE: Currently, only bool, str, int, and float
            types are supported for filtering.
        TODO(sang): Filter on the source side instead for optimization.
        """
        raise NotImplementedError


# TODO(sang): Replace it with Pydantic or gRPC schema (once interface is finalized).
@dataclass(init=True)
class ActorState(StateSchema):
    actor_id: str
    state: str
    class_name: str
    name: str
    pid: int
    serialized_runtime_env: str
    resource_mapping: dict
    death_cause: dict
    is_detached: bool

    @classmethod
    def filterable_columns(cls) -> Set[str]:
        return {"actor_id", "state", "class_name"}


@dataclass(init=True)
class PlacementGroupState(StateSchema):
    placement_group_id: str
    state: str
    name: str
    bundles: dict
    is_detached: bool
    stats: dict

    @classmethod
    def filterable_columns(cls) -> Set[str]:
        return {"placement_group_id", "state"}


@dataclass(init=True)
class NodeState(StateSchema):
    node_id: str
    state: str
    node_name: str
    resources_total: dict

    @classmethod
    def filterable_columns(cls) -> Set[str]:
        return {"node_id", "state"}


class JobState(JobInfo, StateSchema):
    @classmethod
    def filterable_columns(cls) -> Set[str]:
        return {"status", "entrypoint", "error_type"}


@dataclass(init=True)
class WorkerState(StateSchema):
    worker_id: str
    is_alive: str
    worker_type: str
    exit_type: str
    exit_detail: str
    pid: str
    worker_info: dict

    @classmethod
    def filterable_columns(cls) -> Set[str]:
        return {"worker_id", "is_alive", "worker_type", "exit_type", "pid"}


@dataclass(init=True)
class TaskState(StateSchema):
    task_id: str
    name: str
    scheduling_state: str
    type: str
    language: str
    func_or_class_name: str
    required_resources: dict
    runtime_env_info: str

    @classmethod
    def filterable_columns(cls) -> Set[str]:
        return {
            "task_id",
            "name",
            "scheduling_state",
        }


@dataclass(init=True)
class ObjectState(StateSchema):
    object_id: str
    pid: int
    node_ip_address: str
    object_size: int
    reference_type: str
    call_site: str
    task_status: str
    local_ref_count: int
    pinned_in_memory: int
    submitted_task_ref_count: int
    contained_in_owned: int
    type: str

    @classmethod
    def filterable_columns(cls) -> Set[str]:
        return {
            "object_id",
            "node_ip_address",
            "reference_type",
            "task_status",
            "type",
            "pid",
        }


@dataclass(init=True)
class RuntimeEnvState(StateSchema):
    runtime_env: str
    ref_cnt: int
    success: bool
    error: str
    creation_time_ms: float
    node_id: str

    @classmethod
    def filterable_columns(cls) -> Set[str]:
        return {
            "node_id",
            "runtime_env",
            "success",
        }


@dataclass(init=True)
class ListApiResponse:
    # Returned data. None if no data is returned.
    result: Union[
        Dict[
            str,
            Union[
                ActorState,
                PlacementGroupState,
                NodeState,
                JobInfo,
                WorkerState,
                TaskState,
                ObjectState,
            ],
        ],
        List[RuntimeEnvState],
    ] = None
    # List API can have a partial failure if queries to
    # all sources fail. For example, getting object states
    # require to ping all raylets, and it is possible some of
    # them fails. Note that it is impossible to guarantee high
    # availability of data because ray's state information is
    # not replicated.
    partial_failure_warning: str = ""
