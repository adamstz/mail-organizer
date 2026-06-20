import os


def resolve_localhost(url: str) -> str:
    """Replace localhost with host.docker.internal when running inside a Docker container."""
    if os.path.exists("/.dockerenv"):
        return url.replace("localhost", "host.docker.internal")
    return url


def get_ollama_host() -> str:
    return resolve_localhost(os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
