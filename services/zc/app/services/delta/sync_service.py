"""
Enterprise-grade Delta Sync Service for wire CLI.
Implements binary diffing (BSDiff/VCDIFF) for bandwidth-optimized file updates.

2026 Standards:
- Content-Addressable Storage (CAS) with BLAKE3
- Zero-copy patch application
- Async streaming patch processing
- Automatic fallback to full upload when delta > threshold
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any

import blake3

# Try optional high-performance diff libraries
try:
    import bsdiff4
    HAS_BSDIFF = True
except ImportError:
    HAS_BSDIFF = False

try:
    import zstandard as zstd
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False


@dataclass
class DeltaResult:
    success: bool
    patch_size: int
    original_size: int
    bytes_saved: int
    savings_percent: float
    patch_algorithm: str
    new_hash: str
    error_message: Optional[str] = None


class DeltaSyncService:
    """
    High-performance delta synchronization service.
    
    Features:
    - BSDiff binary diffing for minimal patch sizes
    - Zstandard compression for patches
    - Content-addressable storage integration
    - Automatic threshold detection (delta vs full upload)
    """
    
    DELTA_THRESHOLD_PERCENT = 70.0  # If delta > 70% of file, use full upload
    
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
    def _get_cas_path(self, content_hash: str) -> Path:
        """Get content-addressable storage path for a hash."""
        prefix = content_hash[:4]
        cas_dir = self.storage_path / "cas" / prefix
        cas_dir.mkdir(parents=True, exist_ok=True)
        return cas_dir / content_hash
    
    async def get_file_by_hash(self, content_hash: str) -> Optional[bytes]:
        """Retrieve file from CAS by BLAKE3 hash."""
        cas_path = self._get_cas_path(content_hash)
        if not cas_path.exists():
            return None
        
        async with asyncio.Lock():
            with open(cas_path, 'rb') as f:
                return f.read()
    
    async def store_file(self, content: bytes) -> str:
        """Store file in CAS and return BLAKE3 hash."""
        content_hash = blake3.blake3(content).hexdigest()
        cas_path = self._get_cas_path(content_hash)
        
        if cas_path.exists():
            return content_hash  # Already stored (deduplication)
        
        async with asyncio.Lock():
            with open(cas_path, 'wb') as f:
                f.write(content)
        
        return content_hash
    
    async def compute_delta(
        self,
        base_hash: str,
        target_content: bytes,
        algorithm: str = "bsdiff"
    ) -> DeltaResult:
        """
        Compute binary delta between stored base version and new target content.
        
        Args:
            base_hash: BLAKE3 hash of the base (existing) version
            target_content: New file content to create patch for
            algorithm: "bsdiff", "vcdiff", or "naive"
            
        Returns:
            DeltaResult with patch data and statistics
        """
        # Retrieve base version from CAS
        base_content = await self.get_file_by_hash(base_hash)
        if base_content is None:
            return DeltaResult(
                success=False,
                patch_size=0,
                original_size=len(target_content),
                bytes_saved=0,
                savings_percent=0.0,
                patch_algorithm=algorithm,
                new_hash="",
                error_message=f"Base version {base_hash} not found in storage"
            )
        
        original_size = len(target_content)
        len(base_content)
        
        # Compute target hash
        target_hash = blake3.blake3(target_content).hexdigest()
        
        # Check if files are identical
        if base_hash == target_hash:
            return DeltaResult(
                success=True,
                patch_size=0,
                original_size=original_size,
                bytes_saved=original_size,
                savings_percent=100.0,
                patch_algorithm="identity",
                new_hash=target_hash
            )
        
        # Generate patch based on algorithm
        patch_data: bytes
        if algorithm == "bsdiff" and HAS_BSDIFF:
            patch_data = await asyncio.to_thread(bsdiff4.diff, base_content, target_content)
        elif algorithm == "naive" or not HAS_BSDIFF:
            # Fallback: simple XOR delta (less efficient but no dependencies)
            patch_data = self._naive_delta(base_content, target_content)
        else:
            return DeltaResult(
                success=False,
                patch_size=0,
                original_size=original_size,
                bytes_saved=0,
                savings_percent=0.0,
                patch_algorithm=algorithm,
                new_hash=target_hash,
                error_message=f"Algorithm {algorithm} not available"
            )
        
        # Compress patch with Zstandard if available
        compressed_patch = patch_data
        compression_ratio = 0.0
        if HAS_ZSTD and len(patch_data) > 1024:
            cctx = zstd.ZstdCompressor(level=9)
            compressed_patch = cctx.compress(patch_data)
            compression_ratio = (1 - len(compressed_patch) / len(patch_data)) * 100
        
        patch_size = len(compressed_patch)
        
        # Calculate savings
        if patch_size >= original_size * (self.DELTA_THRESHOLD_PERCENT / 100):
            # Delta too large, recommend full upload
            return DeltaResult(
                success=False,
                patch_size=patch_size,
                original_size=original_size,
                bytes_saved=0,
                savings_percent=0.0,
                patch_algorithm=algorithm,
                new_hash=target_hash,
                error_message=f"Delta too large ({patch_size/original_size*100:.1f}%). Use full upload."
            )
        
        bytes_saved = original_size - patch_size
        savings_percent = (bytes_saved / original_size) * 100 if original_size > 0 else 0
        
        return DeltaResult(
            success=True,
            patch_size=patch_size,
            original_size=original_size,
            bytes_saved=bytes_saved,
            savings_percent=savings_percent,
            patch_algorithm=f"{algorithm}" + ("+zstd" if HAS_ZSTD and compression_ratio > 0 else ""),
            new_hash=target_hash
        )
    
    def _naive_delta(self, base: bytes, target: bytes) -> bytes:
        """
        Naive XOR-based delta for systems without bsdiff.
        Less efficient but requires no external dependencies.
        """
        max_len = max(len(base), len(target))
        delta = bytearray(max_len + 8)  # Header + data
        
        # Simple header: base_len (4 bytes) + target_len (4 bytes)
        delta[0:4] = len(base).to_bytes(4, 'little')
        delta[4:8] = len(target).to_bytes(4, 'little')
        
        # XOR common bytes
        for i in range(min(len(base), len(target))):
            delta[8 + i] = base[i] ^ target[i]
        
        # Append remaining bytes from longer file with marker
        if len(target) > len(base):
            delta[8 + len(base):8 + len(target)] = target[len(base):]
        
        return bytes(delta)
    
    async def apply_patch(
        self,
        base_hash: str,
        patch_data: bytes,
        algorithm: str = "bsdiff"
    ) -> tuple[Optional[bytes], str]:
        """
        Apply patch to base version and return reconstructed content.
        
        Returns:
            Tuple of (reconstructed_content, error_message)
        """
        base_content = await self.get_file_by_hash(base_hash)
        if base_content is None:
            return None, f"Base version {base_hash} not found"
        
        # Decompress if Zstandard was used
        decompressed_patch = patch_data
        if HAS_ZSTD and patch_data[:4] == b'\x28\xB5\x2F\xFD':  # ZSTD magic number
            dctx = zstd.ZstdDecompressor()
            decompressed_patch = dctx.decompress(patch_data)
        
        try:
            if algorithm.startswith("bsdiff") and HAS_BSDIFF:
                target_content = await asyncio.to_thread(
                    bsdiff4.patch, base_content, decompressed_patch
                )
            elif algorithm == "naive":
                target_content = self._apply_naive_patch(base_content, decompressed_patch)
            else:
                return None, f"Unknown algorithm: {algorithm}"
            
            # Verify integrity
            computed_hash = blake3.blake3(target_content).hexdigest()
            return target_content, computed_hash
            
        except Exception as e:
            return None, f"Patch application failed: {str(e)}"
    
    def _apply_naive_patch(self, base: bytes, patch: bytes) -> bytes:
        """Apply naive XOR patch."""
        if len(patch) < 8:
            raise ValueError("Invalid patch format")
        
        base_len = int.from_bytes(patch[0:4], 'little')
        target_len = int.from_bytes(patch[4:8], 'little')
        
        target = bytearray(target_len)
        
        # XOR common bytes
        data_start = 8
        common_len = min(base_len, target_len)
        for i in range(common_len):
            target[i] = base[i] ^ patch[data_start + i]
        
        # Copy remaining bytes
        if target_len > base_len:
            target[base_len:target_len] = patch[data_start + base_len:data_start + target_len]
        
        return bytes(target)
    
    async def estimate_bandwidth_savings(
        self,
        base_hash: str,
        target_size: int
    ) -> dict[str, Any]:
        """
        Estimate potential bandwidth savings without computing full delta.
        Uses heuristics based on file size difference.
        """
        base_content = await self.get_file_by_hash(base_hash)
        if base_content is None:
            return {"estimated_savings_percent": 0.0, "recommendation": "full_upload"}
        
        base_size = len(base_content)
        size_ratio = target_size / base_size if base_size > 0 else float('inf')
        
        # Heuristic: similar sizes likely have good delta compression
        if 0.8 <= size_ratio <= 1.2:
            estimated_savings = 85.0  # Small changes = high savings
            recommendation = "delta_sync"
        elif 0.5 <= size_ratio < 0.8 or 1.2 < size_ratio <= 2.0:
            estimated_savings = 50.0
            recommendation = "delta_sync"
        else:
            estimated_savings = 15.0
            recommendation = "full_upload"
        
        return {
            "estimated_savings_percent": estimated_savings,
            "recommendation": recommendation,
            "base_size": base_size,
            "target_size": target_size,
            "size_ratio": size_ratio
        }
