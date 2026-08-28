# Protocol Buffers package for wire CLI-to-API communication
"""
This package contains generated Protocol Buffer classes from wire.proto.
Generated with: python -m grpc_tools.protoc -Iapp/proto --python_out=app/proto --grpc_python_out=app/proto app/proto/wire.proto
"""

from . import wire_pb2, wire_pb2_grpc  # type: ignore[attr-defined]

__all__ = ["wire_pb2", "wire_pb2_grpc"]
