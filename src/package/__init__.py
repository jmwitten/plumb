"""Public protocol for complete generated construction packages."""

from .model import PackageArtifact, PackageRequest, PackageResult


def build_package(request: PackageRequest) -> PackageResult:
    """Lazily invoke the full builder so manifest/help imports stay light."""
    from .builder import build_package as _build_package

    return _build_package(request)


__all__ = [
    "PackageArtifact",
    "PackageRequest",
    "PackageResult",
    "build_package",
]
