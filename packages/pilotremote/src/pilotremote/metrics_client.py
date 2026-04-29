"""gRPC client for streaming CPU metrics from a remote pilotagent."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import grpc

from pilotremote.gen import pilotmetrics_pb2, pilotmetrics_pb2_grpc


class MetricsClient:
    """Stream CPU samples from a running pilotagent over gRPC.

    Typical usage with an SSH tunnel:
        client = MetricsClient("127.0.0.1:50051")
        for sample in client.stream_cpu(interval_seconds=1.0):
            print(sample.usage_percent, sample.timestamp_ms)
    """

    def __init__(self, address: str) -> None:
        self._address = address

    def stream_cpu(self, interval_seconds: float = 1.0) -> Iterator[Any]:
        """Yield CpuSample messages from the agent until the context is cancelled."""
        with grpc.insecure_channel(self._address) as channel:
            stub = pilotmetrics_pb2_grpc.MetricsStub(channel)  # type: ignore[no-untyped-call]
            request = pilotmetrics_pb2.CpuRequest(interval_seconds=interval_seconds)  # type: ignore[attr-defined]
            yield from stub.StreamCpu(request)
