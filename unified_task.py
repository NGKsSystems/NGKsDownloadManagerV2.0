"""
Enhanced QueueTask for Unified Download Pipeline (Phase 9)
Extends ENGINE BASELINE v2.0 QueueTask to support all download types
"""

from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional
import json

# Import TaskState from queue_manager for compatibility
from queue_manager import TaskState

@dataclass
class UnifiedQueueTask:
    """
    Enhanced QueueTask with support for all download types:
    - HTTP/HTTPS (current ENGINE BASELINE v2.0)
    - yt-dlp/Video downloads  
    - HuggingFace models/datasets
    - Protocol handlers (FTP, SFTP)
    
    BACKWARD COMPATIBILITY: All existing ENGINE BASELINE v2.0 fields preserved
    """
    # ENGINE BASELINE v2.0 FIELDS (LOCKED - DO NOT MODIFY)
    task_id: str
    url: str
    destination: str
    priority: int
    state: TaskState
    created_at: str
    updated_at: str
    mode: str = "auto"
    connections_used: int = 1
    error: Optional[str] = None
    progress: float = 0.0
    speed_bps: float = 0.0
    resume_state_path: Optional[str] = None
    history_id: Optional[str] = None
    # V2.8 retry/backoff fields (LOCKED)
    attempt: int = 0
    max_attempts: int = 3
    next_eligible_at: Optional[str] = None
    last_error: Optional[str] = None
    # V2.8 fairness fields (LOCKED)
    host: Optional[str] = None
    effective_priority: int = 5
    
    # PHASE 9 UNIFIED EXTENSIONS
    download_type: str = "http"  # "http", "youtube", "huggingface", "protocol"
    download_options: Dict[str, Any] = field(default_factory=dict)
    forensics_session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (ENGINE BASELINE v2.0 compatible)"""
        data = asdict(self)
        data['state'] = self.state.value
        # Serialize download_options as JSON for persistence
        data['download_options'] = json.dumps(self.download_options)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnifiedQueueTask':
        """Create from dictionary (ENGINE BASELINE v2.0 compatible)"""
        data = data.copy()
        data['state'] = TaskState(data['state'])
        
        # Handle backward compatibility for existing tasks
        if 'download_type' not in data:
            data['download_type'] = 'http'
        if 'download_options' not in data:
            data['download_options'] = {}
        elif isinstance(data['download_options'], str):
            # Deserialize JSON string
            data['download_options'] = json.loads(data['download_options'])
            
        if 'forensics_session_id' not in data:
            data['forensics_session_id'] = None
            
        return cls(**data)

    def get_download_executor_type(self) -> str:
        """Determine which executor should handle this task"""
        if self.download_type == "http":
            return "download_manager"
        elif self.download_type == "youtube":
            return "youtube_downloader"  
        elif self.download_type == "huggingface":
            return "huggingface_downloader"
        elif self.download_type == "protocol":
            return "protocol_handler"
        else:
            raise ValueError(f"Unknown download_type: {self.download_type}")
    
    def get_type_specific_options(self) -> Dict[str, Any]:
        """Get options specific to download type"""
        return self.download_options.copy()

# Backward compatibility alias
QueueTask = UnifiedQueueTask