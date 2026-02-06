"""
Unified Download Executor (Phase 9)
Routes download tasks to appropriate handlers while preserving ENGINE BASELINE v2.0 semantics
"""

import logging
import os
from pathlib import Path
from typing import Callable, Optional, Any, Dict
from urllib.parse import urlparse

# Import all download handlers
from download_manager import DownloadManager
from youtube_downloader import YouTubeDownloader  
from huggingface_downloader import HuggingFaceDownloader
from protocol_handlers import ProtocolManager
from unified_task import UnifiedQueueTask
from policy_engine import PolicyEngine
# Import TaskState for the class
from queue_manager import TaskState

logger = logging.getLogger("unified_executor")

class UnifiedDownloadExecutor:
    """
    Unified executor that routes download tasks to appropriate handlers
    Maintains ENGINE BASELINE v2.0 compatibility while supporting all download types
    """
    
    def __init__(self, download_manager_config: Dict[str, Any] = None):
        """Initialize with download manager configuration"""
        # Initialize ENGINE BASELINE v2.0 HTTP downloader
        dm_config = download_manager_config or {}
        self.download_manager = DownloadManager(
            max_chunk_size=dm_config.get('max_chunk_size', 8192),
            max_retries=dm_config.get('max_retries', 3),
            enable_multi_connection=dm_config.get('enable_multi_connection', True),
            max_connections=dm_config.get('max_connections', 4),
            debug_logging=dm_config.get('debug_logging', False)
        )
        
        # Initialize specialized downloaders
        self.youtube_downloader = YouTubeDownloader()
        self.huggingface_downloader = HuggingFaceDownloader()
        
        # Initialize protocol manager for FTP, SFTP, etc.
        self.protocol_manager = ProtocolManager()
        
        # Initialize policy engine for OPTION 4 auditability
        self.policy_engine = PolicyEngine()
        
        logger.info("UNIFIED_EXECUTOR | INIT_OK | handlers=[http,youtube,huggingface,protocol]")

    def detect_download_type(self, url: str) -> str:
        """
        Auto-detect download type from URL
        Falls back to ENGINE BASELINE v2.0 HTTP handling if unknown
        """
        try:
            parsed = urlparse(url.lower())
            domain = parsed.netloc.lower()
            
            # YouTube/video detection
            if any(site in domain for site in ['youtube.com', 'youtu.be', 'twitter.com', 'x.com', 
                                              'instagram.com', 'tiktok.com', 'twitch.tv']):
                return "youtube"
            
            # HuggingFace detection  
            if 'huggingface.co' in domain:
                return "huggingface"
                
            # Protocol detection
            if parsed.scheme in ['ftp', 'ftps', 'sftp']:
                return "protocol"
                
            # Default to ENGINE BASELINE v2.0 HTTP
            return "http"
            
        except Exception as e:
            logger.warning(f"URL detection failed: {e}, using HTTP fallback")
            return "http"

    def create_task_for_url(self, task_id: str, url: str, destination: str, 
                           priority: int = 5, **type_options) -> UnifiedQueueTask:
        """
        Create a UnifiedQueueTask with auto-detected download type
        Preserves ENGINE BASELINE v2.0 task creation semantics
        """
        download_type = self.detect_download_type(url)
        
        # Apply download type specific options
        download_options = {}
        if download_type == "youtube":
            download_options = {
                'extract_audio': type_options.get('extract_audio', False),
                'auto_quality': type_options.get('auto_quality', True), 
                'quality': type_options.get('quality', 'best')
            }
        elif download_type == "huggingface":
            download_options = {
                'token': type_options.get('token', None)
            }
        elif download_type == "protocol":
            download_options = type_options.copy()
        
        from datetime import datetime
        now = datetime.now().isoformat()
        
        task = UnifiedQueueTask(
            task_id=task_id,
            url=url,
            destination=destination,
            priority=priority,
            state=TaskState.PENDING,
            created_at=now,
            updated_at=now,
            download_type=download_type,
            download_options=download_options
        )
        
        logger.info(f"TASK_CREATE | {task_id} | type={download_type} | url={url[:50]}...")
        return task

    def execute_download(self, task: UnifiedQueueTask, progress_callback: Optional[Callable] = None) -> bool:
        """
        Execute download using appropriate handler based on task type
        Preserves ENGINE BASELINE v2.0 execution semantics and forensics integration
        """
        try:
            logger.info(f"EXECUTE_START | {task.task_id} | type={task.download_type}")
            
            # Apply policy evaluation (OPTION 4 audit requirement)
            policy_result = self.policy_engine.check_enqueue_policy(
                task.task_id, task.url, task.destination, **task.get_type_specific_options()
            )
            
            if policy_result.action != 'ALLOW':
                error_msg = f"Policy blocked ({policy_result.action}): {policy_result.reason}"
                logger.error(f"POLICY_BLOCKED | {task.task_id} | {error_msg}")
                task.error = error_msg
                return False
            
            # Route to appropriate executor
            executor_type = task.get_download_executor_type()
            
            if executor_type == "download_manager":
                return self._execute_http_download(task, progress_callback)
            elif executor_type == "youtube_downloader":
                return self._execute_youtube_download(task, progress_callback)
            elif executor_type == "huggingface_downloader":
                return self._execute_huggingface_download(task, progress_callback)
            elif executor_type == "protocol_handler":
                return self._execute_protocol_download(task, progress_callback)
            else:
                raise ValueError(f"Unknown executor type: {executor_type}")
                
        except Exception as e:
            error_msg = f"Execution failed: {str(e)}"
            logger.error(f"EXECUTE_ERROR | {task.task_id} | {error_msg}")
            task.error = error_msg
            task.last_error = error_msg
            return False

    def _execute_http_download(self, task: UnifiedQueueTask, progress_callback: Optional[Callable]) -> bool:
        """Execute HTTP download via ENGINE BASELINE v2.0 DownloadManager"""
        try:
            # Use ENGINE BASELINE v2.0 download method
            result = self.download_manager.download(
                task.url, 
                task.destination,
                progress_callback=progress_callback
            )
            
            if result and result.get('status') == 'success':
                task.progress = 100.0
                logger.info(f"HTTP_SUCCESS | {task.task_id}")
                return True
            else:
                task.error = result.get('error', 'HTTP download failed')
                logger.error(f"HTTP_FAILED | {task.task_id} | {task.error}")
                return False
                
        except Exception as e:
            task.error = f"HTTP download error: {str(e)}"
            logger.error(f"HTTP_ERROR | {task.task_id} | {task.error}")
            return False

    def _execute_youtube_download(self, task: UnifiedQueueTask, progress_callback: Optional[Callable]) -> bool:
        """Execute YouTube/video download via YouTubeDownloader"""
        try:
            options = task.get_type_specific_options()
            
            result = self.youtube_downloader.download(
                task.url,
                task.destination,
                progress_callback=progress_callback,
                extract_audio=options.get('extract_audio', False),
                auto_quality=options.get('auto_quality', True),
                quality=options.get('quality', 'best')
            )
            
            if result and result.get('status') == 'success':
                task.progress = 100.0
                logger.info(f"YOUTUBE_SUCCESS | {task.task_id}")
                return True
            else:
                task.error = result.get('error', 'YouTube download failed')
                logger.error(f"YOUTUBE_FAILED | {task.task_id} | {task.error}")
                return False
                
        except Exception as e:
            task.error = f"YouTube download error: {str(e)}"
            logger.error(f"YOUTUBE_ERROR | {task.task_id} | {task.error}")
            return False

    def _execute_huggingface_download(self, task: UnifiedQueueTask, progress_callback: Optional[Callable]) -> bool:
        """Execute HuggingFace download via HuggingFaceDownloader"""
        try:
            options = task.get_type_specific_options()
            
            result = self.huggingface_downloader.download(
                task.url,
                task.destination,
                progress_callback=progress_callback,
                token=options.get('token', None)
            )
            
            # HuggingFaceDownloader returns boolean, not dict
            if result:
                task.progress = 100.0
                logger.info(f"HUGGINGFACE_SUCCESS | {task.task_id}")
                return True
            else:
                task.error = "HuggingFace download failed"
                logger.error(f"HUGGINGFACE_FAILED | {task.task_id}")
                return False
                
        except Exception as e:
            task.error = f"HuggingFace download error: {str(e)}"
            logger.error(f"HUGGINGFACE_ERROR | {task.task_id} | {task.error}")
            return False

    def _execute_protocol_download(self, task: UnifiedQueueTask, progress_callback: Optional[Callable]) -> bool:
        """Execute protocol download via ProtocolManager"""
        try:
            handler = self.protocol_manager.get_handler(task.url)
            if not handler:
                task.error = f"No handler available for protocol: {task.url}"
                logger.error(f"PROTOCOL_NO_HANDLER | {task.task_id}")
                return False
            
            options = task.get_type_specific_options()
            
            result = handler.download(
                task.url,
                task.destination,
                progress_callback=progress_callback,
                **options
            )
            
            if result:
                task.progress = 100.0
                logger.info(f"PROTOCOL_SUCCESS | {task.task_id}")
                return True
            else:
                task.error = "Protocol download failed"
                logger.error(f"PROTOCOL_FAILED | {task.task_id}")
                return False
                
        except Exception as e:
            task.error = f"Protocol download error: {str(e)}"
            logger.error(f"PROTOCOL_ERROR | {task.task_id} | {task.error}")
            return False