"""Local immutable objects. Keys are UUIDs, never caller-provided filesystem paths."""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from typing import BinaryIO
import uuid


@dataclass(frozen=True)
class BlobRef:
    project_id: uuid.UUID
    object_id: uuid.UUID
    sha256: str
    size: int


class LocalBlobStore:
    def __init__(self, root: Path):
        if not root.is_absolute():
            raise ValueError('Blob root must be absolute.')
        root.mkdir(parents=True, exist_ok=True)
        if root.is_symlink():
            raise ValueError('Blob root must not be a symlink.')
        self.root = root.resolve()

    @staticmethod
    def identity(value):
        return str(uuid.UUID(str(value)))

    def path(self, project_id, object_id):
        project = self.root / self.identity(project_id)
        if project.is_symlink():
            raise ValueError('Symlink object directories are not allowed.')
        project.mkdir(exist_ok=True)
        path = project / self.identity(object_id)
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise ValueError('Object path escapes BlobStore.')
        return path

    def put(self, project_id, source: BinaryIO, *, expected_sha256: str, max_bytes: int):
        if max_bytes < 1:
            raise ValueError('A positive object size limit is required.')
        if len(expected_sha256) != 64 or any(c not in '0123456789abcdef' for c in expected_sha256):
            raise ValueError('An explicit lowercase SHA256 checksum is required.')
        object_id = uuid.uuid4()
        target = self.path(project_id, object_id)
        temporary = target.with_suffix('.partial')
        digest, size = hashlib.sha256(), 0
        try:
            with temporary.open('xb') as output:
                while chunk := source.read(min(1048576, max_bytes - size + 1)):
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError('Object exceeds configured size limit.')
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            if digest.hexdigest() != expected_sha256:
                raise ValueError('Object checksum mismatch.')
            # Atomic no-clobber finalize on NTFS and supported local Unix filesystems.
            # A crash before link leaves only .partial; after link the object is complete.
            os.link(temporary, target)
            if os.name != 'nt':
                directory = os.open(target.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            return BlobRef(uuid.UUID(str(project_id)), object_id, digest.hexdigest(), size)
        finally:
            temporary.unlink(missing_ok=True)

    def open(self, project_id, object_id):
        return self.path(project_id, object_id).open('rb')

    def verify(self, ref: BlobRef):
        digest, size = hashlib.sha256(), 0
        with self.open(ref.project_id, ref.object_id) as source:
            while chunk := source.read(1048576):
                size += len(chunk)
                digest.update(chunk)
        return size == ref.size and digest.hexdigest() == ref.sha256
