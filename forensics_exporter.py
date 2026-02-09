#!/usr/bin/env python3
"""
STEP 6: Observability + Forensics Export
NGK's Download Manager V2.0 - Read-Only Diagnostic Export

CRITICAL: Zero behavior change to download flow
Only reads existing state/logs, writes export files
"""

import os
import json
import zipfile
import tempfile
import subprocess
import logging
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import uuid

logger = logging.getLogger(__name__)

@dataclass
class SessionMetadata:
    """Session tracking for forensic continuity"""
    session_id: str
    created_at: str
    app_version: str
    python_version: str
    git_sha: str
    git_branch: str
    platform_info: str

@dataclass 
class TaskEvent:
    """Individual task event for timeline"""
    timestamp: str
    task_id: str
    event_type: str  # POLICY, ENQUEUE, START, RETRY, RESUME, HASH, ATOMIC, COMPLETE, FAIL
    component: str   # policy, queue, download_manager
    action: str      # CHECK, ALLOW, DENY, START, etc.
    details: Dict[str, Any]

@dataclass
class TaskTimeline:
    """Complete timeline for a single task"""
    task_id: str
    created_at: str
    final_status: str
    events: List[TaskEvent]
    duration_seconds: Optional[float] = None

class ForensicsExporter:
    """
    Read-only forensics exporter
    Creates comprehensive diagnostic packages for troubleshooting
    """
    
    def __init__(self, session_metadata: SessionMetadata = None):
        self.session_metadata = session_metadata or self._create_session_metadata()
        self.logger = logging.getLogger("forensics")
        self.export_base_path = Path("exports")
        self.export_base_path.mkdir(exist_ok=True)
        
        self.logger.info(f"FORENSICS | SESSION_START | session_id={self.session_metadata.session_id}")
        
    def _create_session_metadata(self) -> SessionMetadata:
        """Create session tracking metadata"""
        session_id = f"session_{int(datetime.now().timestamp())}_{str(uuid.uuid4())[:8]}"
        
        # Get git information
        try:
            git_sha = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], 
                cwd=".", 
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except:
            git_sha = "unknown"
            
        try:
            git_branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], 
                cwd=".", 
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except:
            git_branch = "unknown"
        
        return SessionMetadata(
            session_id=session_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            app_version="v2.0-step6",
            python_version=platform.python_version(),
            git_sha=git_sha,
            git_branch=git_branch,
            platform_info=f"{platform.system()} {platform.release()}"
        )
    
    def export_diagnostic_pack(self) -> str:
        """
        Create complete forensic diagnostic pack
        Returns path to created ZIP file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_filename = f"ngk_diagnostics_{self.session_metadata.session_id}_{timestamp}.zip"
        export_path = self.export_base_path / export_filename
        
        self.logger.info(f"FORENSICS | EXPORT_START | file={export_filename}")
        
        try:
            with zipfile.ZipFile(export_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                # 1. Session metadata
                self._add_session_metadata(zf)
                
                # 2. Current logs
                self._add_log_files(zf)
                
                # 3. Queue persistence files
                self._add_queue_state_files(zf)
                
                # 4. Resume state files
                self._add_resume_state_files(zf)
                
                # 5. Policy configuration
                self._add_policy_config(zf)
                
                # 6. Build metadata
                self._add_build_metadata(zf)
                
                # 7. Per-task timelines
                self._add_task_timelines(zf)
                
            self.logger.info(f"FORENSICS | EXPORT_COMPLETE | file={export_filename} | size={export_path.stat().st_size}")
            return str(export_path)
            
        except Exception as e:
            self.logger.error(f"FORENSICS | EXPORT_FAIL | error={str(e)}")
            raise
    
    def _add_session_metadata(self, zf: zipfile.ZipFile):
        """Add session metadata to export"""
        metadata_json = json.dumps(asdict(self.session_metadata), indent=2)
        zf.writestr("session_metadata.json", metadata_json)
        
    def _add_log_files(self, zf: zipfile.ZipFile):
        """Add current log files to export"""
        # Current UI log
        ui_log_path = Path("logs/ui.log")
        if ui_log_path.exists():
            zf.write(ui_log_path, f"logs/{ui_log_path.name}")
            
        # Find latest DL Manager logs  
        dl_logs_dir = Path.home() / "Downloads" / "DL Manager Logs"
        if dl_logs_dir.exists():
            log_files = list(dl_logs_dir.glob("NGKs_DownloadManager_Log_*.log"))
            if log_files:
                # Get most recent log file
                latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
                zf.write(latest_log, f"logs/{latest_log.name}")
                
    def _add_queue_state_files(self, zf: zipfile.ZipFile):
        """Add queue persistence files to export"""
        queue_state_path = Path("data/queue_state.json")
        if queue_state_path.exists():
            zf.write(queue_state_path, f"queue/{queue_state_path.name}")
            
    def _add_resume_state_files(self, zf: zipfile.ZipFile):
        """Add any resume state files to export"""
        # Look for .resume files in downloads directory
        downloads_dir = Path.home() / "Downloads" / "NGK_Downloads"
        if downloads_dir.exists():
            resume_files = list(downloads_dir.glob("*.resume"))
            for resume_file in resume_files:
                zf.write(resume_file, f"resume_states/{resume_file.name}")
                
    def _add_policy_config(self, zf: zipfile.ZipFile):
        """Add policy configuration to export"""
        policy_path = Path("config/policy.json")
        if policy_path.exists():
            zf.write(policy_path, f"policy/{policy_path.name}")
            
        # Add effective policy snapshot (runtime resolved)
        try:
            from policy_engine import PolicyEngine
            policy_engine = PolicyEngine()
            effective_policy = policy_engine.get_policy_summary()
            
            policy_json = json.dumps(effective_policy, indent=2)
            zf.writestr("policy/effective_policy_snapshot.json", policy_json)
        except Exception as e:
            self.logger.warning(f"Could not capture effective policy: {e}")
            
    def _add_build_metadata(self, zf: zipfile.ZipFile):
        """Add build and version metadata to export"""
        build_info = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "git_sha": self.session_metadata.git_sha,
            "git_branch": self.session_metadata.git_branch,
            "python_version": self.session_metadata.python_version,
            "platform": self.session_metadata.platform_info,
            "app_version": self.session_metadata.app_version,
            "session_id": self.session_metadata.session_id
        }
        
        # Add package versions if available
        try:
            import pkg_resources
            installed_packages = []
            for req in ["requests", "PySide6", "qt6tools"]:
                try:
                    pkg = pkg_resources.get_distribution(req)
                    installed_packages.append(f"{pkg.project_name}=={pkg.version}")
                except:
                    pass
            build_info["key_packages"] = installed_packages
        except:
            pass
            
        build_json = json.dumps(build_info, indent=2)
        zf.writestr("build_metadata.json", build_json)
        
    def _add_task_timelines(self, zf: zipfile.ZipFile):
        """Add per-task timelines to export"""
        try:
            timelines = self._build_task_timelines()
            timelines_json = json.dumps([asdict(t) for t in timelines], indent=2, default=str)
            zf.writestr("timelines/per_task_timelines.json", timelines_json)
            
            # Add summary timeline
            summary = self._create_timeline_summary(timelines)
            summary_json = json.dumps(summary, indent=2)
            zf.writestr("timelines/timeline_summary.json", summary_json)
            
        except Exception as e:
            self.logger.warning(f"Could not build task timelines: {e}")
            
    def _build_task_timelines(self) -> List[TaskTimeline]:
        """Build ordered timeline for each task from logs"""
        timelines = []
        
        # Parse current UI log
        ui_log_path = Path("logs/ui.log")
        if ui_log_path.exists():
            task_events = self._parse_log_for_task_events(ui_log_path)
            
            # Group events by task_id
            task_groups = {}
            for event in task_events:
                if event.task_id not in task_groups:
                    task_groups[event.task_id] = []
                task_groups[event.task_id].append(event)
                
            # Create timeline for each task
            for task_id, events in task_groups.items():
                events.sort(key=lambda e: e.timestamp)
                
                # Determine final status
                final_status = "UNKNOWN"
                for event in reversed(events):
                    if event.event_type in ["COMPLETE", "FAIL"]:
                        final_status = event.event_type
                        break
                        
                # Calculate duration if possible
                duration = None
                if len(events) >= 2:
                    try:
                        start_time = datetime.fromisoformat(events[0].timestamp.replace('Z', '+00:00'))
                        end_time = datetime.fromisoformat(events[-1].timestamp.replace('Z', '+00:00'))
                        duration = (end_time - start_time).total_seconds()
                    except:
                        pass
                        
                timeline = TaskTimeline(
                    task_id=task_id,
                    created_at=events[0].timestamp if events else datetime.now(timezone.utc).isoformat(),
                    final_status=final_status,
                    events=events,
                    duration_seconds=duration
                )
                timelines.append(timeline)
                
        return timelines
        
    def _parse_log_for_task_events(self, log_path: Path) -> List[TaskEvent]:
        """Parse log file to extract task events"""
        events = []
        
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                        
                    # Parse log line format: timestamp - logger - level - message
                    parts = line.split(' - ', 3)
                    if len(parts) < 4:
                        continue
                        
                    timestamp_str, logger_name, level, message = parts
                    
                    # Convert timestamp to ISO format
                    try:
                        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
                        timestamp_iso = timestamp.replace(tzinfo=timezone.utc).isoformat()
                    except:
                        timestamp_iso = datetime.now(timezone.utc).isoformat()
                        
                    # Extract task events based on log patterns
                    task_event = self._extract_task_event(timestamp_iso, logger_name, message)
                    if task_event:
                        events.append(task_event)
                        
        except Exception as e:
            self.logger.warning(f"Error parsing log {log_path}: {e}")
            
        return events
        
    def _extract_task_event(self, timestamp: str, logger_name: str, message: str) -> Optional[TaskEvent]:
        """Extract task event from log message"""
        
        # POLICY events
        if "POLICY |" in message and "task_id=" in message:
            task_id = self._extract_value(message, "task_id")
            if "CHECK" in message:
                return TaskEvent(timestamp, task_id, "POLICY", "policy", "CHECK", {"message": message})
            elif "ALLOW" in message:
                return TaskEvent(timestamp, task_id, "POLICY", "policy", "ALLOW", {"message": message})
            elif "DENY" in message:
                return TaskEvent(timestamp, task_id, "POLICY", "policy", "DENY", {"message": message})
                
        # HASH events
        if "HASH |" in message and "task_id=" in message:
            task_id = self._extract_value(message, "task_id")
            if "START" in message:
                return TaskEvent(timestamp, task_id, "HASH", "download_manager", "START", {"message": message})
            elif "FINAL_OK" in message:
                return TaskEvent(timestamp, task_id, "HASH", "download_manager", "FINAL_OK", {"message": message})
                
        # ATOMIC events  
        if "ATOMIC |" in message and ("task_id=" in message or "final=" in message):
            task_id = self._extract_value(message, "task_id") or "unknown"
            if "START" in message:
                return TaskEvent(timestamp, task_id, "ATOMIC", "download_manager", "START", {"message": message})
            elif "COMMIT" in message:
                return TaskEvent(timestamp, task_id, "ATOMIC", "download_manager", "COMMIT", {"message": message})
                
        # RESUME events
        if "RESUME |" in message and "task_id=" in message:
            task_id = self._extract_value(message, "task_id")
            if "DETECTED" in message:
                return TaskEvent(timestamp, task_id, "RESUME", "download_manager", "DETECTED", {"message": message})
            elif "VALIDATED" in message:
                return TaskEvent(timestamp, task_id, "RESUME", "download_manager", "VALIDATED", {"message": message})
                
        # Queue events
        if "ENQUEUE" in message and "task_id=" in message:
            task_id = self._extract_value(message, "task_id") 
            return TaskEvent(timestamp, task_id, "ENQUEUE", "queue", "ENQUEUE", {"message": message})
            
        if "START_WORKER" in message and "task_id=" in message:
            task_id = self._extract_value(message, "task_id")
            return TaskEvent(timestamp, task_id, "START", "queue", "START_WORKER", {"message": message})
            
        if "DOWNLOAD_COMPLETE" in message and "task_id=" in message:
            task_id = self._extract_value(message, "task_id") 
            return TaskEvent(timestamp, task_id, "COMPLETE", "queue", "COMPLETE", {"message": message})
            
        if "DOWNLOAD_FAILED" in message and "task_id=" in message:
            task_id = self._extract_value(message, "task_id")
            return TaskEvent(timestamp, task_id, "FAIL", "queue", "FAIL", {"message": message})
            
        return None
        
    def _extract_value(self, message: str, key: str) -> Optional[str]:
        """Extract value from log message key=value format"""
        try:
            if f"{key}=" in message:
                start = message.find(f"{key}=") + len(key) + 1
                end = message.find(" ", start)
                if end == -1:
                    end = message.find("|", start)
                if end == -1:
                    end = len(message)
                return message[start:end].strip()
        except:
            pass
        return None
        
    def _create_timeline_summary(self, timelines: List[TaskTimeline]) -> Dict[str, Any]:
        """Create high-level timeline summary"""
        total_tasks = len(timelines)
        completed_tasks = sum(1 for t in timelines if t.final_status == "COMPLETE")
        failed_tasks = sum(1 for t in timelines if t.final_status == "FAIL")
        
        summary = {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "failed_tasks": failed_tasks,
            "unknown_status": total_tasks - completed_tasks - failed_tasks,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_metadata.session_id
        }
        
        # Add duration statistics
        durations = [t.duration_seconds for t in timelines if t.duration_seconds is not None]
        if durations:
            summary["duration_stats"] = {
                "min_seconds": min(durations),
                "max_seconds": max(durations), 
                "avg_seconds": sum(durations) / len(durations)
            }
            
        return summary


# Global session instance
_session_metadata = None

def get_session_metadata() -> SessionMetadata:
    """Get or create global session metadata"""
    global _session_metadata
    if _session_metadata is None:
        _session_metadata = ForensicsExporter()._create_session_metadata()
        logger.info(f"FORENSICS | SESSION_CREATED | session_id={_session_metadata.session_id}")
    return _session_metadata

def export_diagnostics() -> str:
    """Export diagnostic pack - main entry point"""
    session = get_session_metadata()
    exporter = ForensicsExporter(session)
    return exporter.export_diagnostic_pack()

if __name__ == "__main__":
    # CLI entry point
    print("NGK's Download Manager V2.0 - Forensics Export")
    print("=" * 50)
    
    try:
        export_path = export_diagnostics()
        print(f"✅ Diagnostic pack created: {export_path}")
        
        # Show contents
        print(f"\n📦 Export contents:")
        import zipfile
        with zipfile.ZipFile(export_path, 'r') as zf:
            for info in zf.filelist:
                print(f"  {info.filename} ({info.file_size} bytes)")
                
    except Exception as e:
        print(f"❌ Export failed: {e}")
        sys.exit(1)