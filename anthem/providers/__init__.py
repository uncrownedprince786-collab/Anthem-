"""Backend registry.

Two ways to get audio, both free and neither needing an account:

* acestep - ACE-Step running on this PC. Nothing leaves the machine.
* file    - music you already have, from anywhere.

Paid API backends were removed deliberately. This project is local and
free by design; see README.md.
"""

from .base import Provider, ProviderError, Request, Track
from .local_acestep import LocalAceStepProvider
from .local_file import LocalFileProvider

REGISTRY = {
    LocalAceStepProvider.name: LocalAceStepProvider,
    LocalFileProvider.name: LocalFileProvider,
}

# Local generation first: it is what this project is for.
ORDER = [LocalAceStepProvider.name, LocalFileProvider.name]


def get(name, settings):
    try:
        return REGISTRY[name](settings)
    except KeyError:
        raise ProviderError(
            "Unknown provider '%s'. Pick one of: %s"
            % (name, ", ".join(ORDER))) from None


def labels():
    return [(n, REGISTRY[n].label) for n in ORDER]


__all__ = ["Provider", "ProviderError", "Request", "Track",
           "REGISTRY", "ORDER", "get", "labels"]
