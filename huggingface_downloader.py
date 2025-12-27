"""
Hugging Face Model and Dataset Downloader
Handles authentication and downloads from Hugging Face Hub
"""

import os
import requests
from huggingface_hub import HfApi, hf_hub_download, snapshot_download, login, logout
from huggingface_hub.utils import RepositoryNotFoundError, RevisionNotFoundError
from urllib.parse import urlparse, unquote
import time
import threading
from pathlib import Path
import json

class HuggingFaceDownloader:
    def __init__(self):
        self.api = HfApi()
        self.active_downloads = {}
        
    def download(self, url, destination, progress_callback=None, token=None):
        """
        Download model or dataset from Hugging Face
        
        Args:
            url: Hugging Face URL (model or dataset)
            destination: Destination folder
            progress_callback: Function to call with progress updates
            token: HF authentication token
            
        Returns:
            bool: True if download successful, False otherwise
        """
        try:
            # Parse HF URL
            repo_info = self._parse_hf_url(url)
            if not repo_info:
                raise ValueError(f"Invalid Hugging Face URL: {url}")
            
            repo_id = repo_info['repo_id']
            repo_type = repo_info['repo_type']
            filename = repo_info.get('filename')
            
            if progress_callback:
                progress_callback({
                    'filename': f"Parsing {repo_id}",
                    'progress': "0%",
                    'speed': "0 B/s",
                    'status': 'Parsing URL'
                })
            
            # Set up authentication if token provided
            if token:
                os.environ['HUGGINGFACE_HUB_TOKEN'] = token
                try:
                    login(token=token)
                except Exception as e:
                    print(f"Warning: Could not login with token: {e}")
            
            # Create destination directory
            if filename:
                # For single file downloads, use the repo name as folder
                repo_folder_name = repo_id.replace('/', '_')
                repo_dest = os.path.join(destination, repo_folder_name)
            else:
                # For full repo downloads, use repo name as folder
                repo_folder_name = repo_id.replace('/', '_')
                repo_dest = os.path.join(destination, repo_folder_name)
            
            os.makedirs(repo_dest, exist_ok=True)
            
            if progress_callback:
                progress_callback({
                    'filename': filename if filename else repo_id,
                    'progress': "0%",
                    'speed': "0 B/s",
                    'status': 'Initializing'
                })
            
            # Download specific file or entire repository
            if filename:
                success = self._download_single_file(
                    repo_id, filename, repo_dest, repo_type, progress_callback
                )
            else:
                success = self._download_repository(
                    repo_id, repo_dest, repo_type, progress_callback
                )
            
            if success and progress_callback:
                progress_callback({
                    'filename': filename if filename else repo_id,
                    'progress': "100%",
                    'speed': "0 B/s",
                    'status': 'Completed'
                })
            
            # Return proper result dictionary
            if success:
                filepath = os.path.join(repo_dest, filename) if filename else repo_dest
                return {
                    'status': 'success',
                    'filepath': filepath,
                    'repo_id': repo_id,
                    'filename': filename
                }
            else:
                return {
                    'status': 'error',
                    'error': 'Download failed',
                    'repo_id': repo_id,
                    'filename': filename
                }
            
        except Exception as e:
            error_msg = str(e)
            if "Repository not found" in error_msg:
                error_msg = f"Repository '{repo_info.get('repo_id', 'unknown')}' not found or is private"
            elif "File not found" in error_msg:
                error_msg = f"File '{repo_info.get('filename', 'unknown')}' not found in repository"
            elif "Invalid Hugging Face URL" in error_msg:
                error_msg = "Invalid Hugging Face URL format"
            
            if progress_callback:
                progress_callback({
                    'filename': repo_info.get('repo_id', 'Unknown') if 'repo_info' in locals() else 'Unknown',
                    'progress': "0%",
                    'speed': "0 B/s",
                    'status': f'Error: {error_msg}'
                })
            return {
                'status': 'error',
                'error': error_msg,
                'repo_id': repo_info.get('repo_id', 'Unknown') if 'repo_info' in locals() else 'Unknown',
                'filename': repo_info.get('filename') if 'repo_info' in locals() else None
            }
    
    def _download_single_file(self, repo_id, filename, destination, repo_type, progress_callback):
        """Download a single file from HF repository with progress tracking"""
        try:
            if progress_callback:
                progress_callback({
                    'filename': filename,
                    'progress': "0%",
                    'speed': "0 B/s",
                    'status': 'Starting download'
                })
            
            # Construct direct download URL
            if repo_type == 'dataset':
                download_url = f"https://huggingface.co/datasets/{repo_id}/resolve/main/{filename}"
            elif repo_type == 'space':
                download_url = f"https://huggingface.co/spaces/{repo_id}/resolve/main/{filename}"
            else:  # model
                download_url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
            
            # Use requests for download with progress tracking
            import requests
            import time
            
            # Get headers for authentication if token exists
            headers = {}
            if 'HUGGINGFACE_HUB_TOKEN' in os.environ:
                headers['Authorization'] = f"Bearer {os.environ['HUGGINGFACE_HUB_TOKEN']}"
            
            # First, try to get file info with HEAD request
            try:
                head_response = requests.head(download_url, headers=headers, allow_redirects=True)
                total_size = int(head_response.headers.get('content-length', 0))
            except:
                total_size = 0
            
            if progress_callback and total_size > 0:
                progress_callback({
                    'filename': f"{filename} ({self._format_size(total_size)})",
                    'progress': "0%",
                    'speed': "0 B/s",
                    'status': 'Connecting'
                })
            
            # Start download
            response = requests.get(download_url, headers=headers, stream=True)
            response.raise_for_status()
            
            # If we didn't get size from HEAD, try from GET response
            if total_size == 0:
                total_size = int(response.headers.get('content-length', 0))
            
            # Create full file path
            file_path = os.path.join(destination, filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Use larger chunk size for better performance
            chunk_size = 64 * 1024  # 64KB chunks for better performance
            
            # Download with progress tracking
            downloaded_size = 0
            start_time = time.time()
            last_update = start_time
            
            with open(file_path, 'wb') as f:
                try:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            
                            # Update progress every 0.5 seconds
                            current_time = time.time()
                            if current_time - last_update >= 0.5:
                                elapsed_time = current_time - start_time
                                if elapsed_time > 0:
                                    speed = downloaded_size / elapsed_time
                                    speed_str = self._format_speed(speed)
                                else:
                                    speed_str = "0 B/s"
                                
                                if progress_callback:
                                    try:
                                        if total_size > 0:
                                            progress_pct = (downloaded_size / total_size) * 100
                                            progress_str = f"{progress_pct:.1f}%"
                                            
                                            # Calculate ETA
                                            if speed > 0:
                                                remaining_bytes = total_size - downloaded_size
                                                eta_seconds = remaining_bytes / speed
                                                eta_str = self._format_time(eta_seconds)
                                            else:
                                                eta_str = "Unknown"
                                            
                                            # Enhanced filename with size info
                                            filename_display = f"{filename} ({self._format_size(downloaded_size)}/{self._format_size(total_size)})"
                                            speed_display = f"{speed_str} - ETA: {eta_str}"
                                        else:
                                            progress_str = self._format_size(downloaded_size)
                                            filename_display = f"{filename} ({progress_str})"
                                            speed_display = speed_str
                                        
                                        progress_callback({
                                            'filename': filename_display,
                                            'progress': progress_str,
                                            'speed': speed_display,
                                            'status': 'Downloading'
                                        })
                                    except Exception as callback_error:
                                        # Don't let callback errors stop the download
                                        print(f"Progress callback error: {callback_error}")
                                
                                last_update = current_time
                except KeyboardInterrupt:
                    print("Download interrupted by user")
                    return False
                except Exception as download_error:
                    print(f"Download error: {download_error}")
                    return False
            
            # Final progress update
            if progress_callback:
                if total_size > 0:
                    filename_display = f"{filename} ({self._format_size(total_size)})"
                else:
                    filename_display = f"{filename} ({self._format_size(downloaded_size)})"
                
                progress_callback({
                    'filename': filename_display,
                    'progress': "100%",
                    'speed': "0 B/s",
                    'status': 'Downloaded'
                })
            
            return True
            
        except Exception as e:
            print(f"Error downloading file {filename}: {e}")
            if progress_callback:
                progress_callback({
                    'filename': filename,
                    'progress': "0%",
                    'speed': "0 B/s",
                    'status': f'Error: {str(e)}'
                })
            return False
    
    def _format_speed(self, bytes_per_second):
        """Format download speed in human readable format"""
        return f"{self._format_size(bytes_per_second)}/s"
    
    def _format_time(self, seconds):
        """Format time in human readable format"""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes:.0f}m {secs:.0f}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours:.0f}h {minutes:.0f}m"
    
    def _download_repository(self, repo_id, destination, repo_type, progress_callback):
        """Download entire repository from HF"""
        try:
            # Get repository info
            repo_info = self.get_repository_info(repo_id, repo_type)
            if not repo_info:
                return False
            
            total_files = len(repo_info.get('files', []))
            downloaded_files = 0
            
            def file_progress_callback(file_info):
                nonlocal downloaded_files
                downloaded_files += 1
                progress = (downloaded_files / total_files) * 100 if total_files > 0 else 0
                
                if progress_callback:
                    progress_callback({
                        'filename': repo_id,
                        'progress': f"{progress:.1f}%",
                        'speed': "0 B/s",
                        'status': f'Downloading ({downloaded_files}/{total_files})'
                    })
            
            # Download repository
            snapshot_download(
                repo_id=repo_id,
                repo_type=repo_type,
                local_dir=destination,
                local_dir_use_symlinks=False
            )
            
            return True
            
        except Exception as e:
            return False
    
    def _parse_hf_url(self, url):
        """Parse Hugging Face URL to extract repo info"""
        try:
            parsed = urlparse(url)
            if 'huggingface.co' not in parsed.netloc:
                return None
            
            path_parts = [p for p in parsed.path.split('/') if p]
            
            if len(path_parts) < 2:
                return None
            
            # Determine repo type and remove type indicators from path
            repo_type = 'model'  # default
            if len(path_parts) > 0 and path_parts[0] == 'datasets':
                repo_type = 'dataset'
                path_parts = path_parts[1:]  # Remove 'datasets' from path
            elif len(path_parts) > 0 and path_parts[0] == 'spaces':
                repo_type = 'space'
                path_parts = path_parts[1:]  # Remove 'spaces' from path
            
            # Extract repo_id
            if repo_type == 'dataset' and len(path_parts) >= 1:
                # Datasets can have single names or org/name format
                if len(path_parts) == 1:
                    repo_id = path_parts[0]  # e.g., 'squad'
                else:
                    repo_id = f"{path_parts[0]}/{path_parts[1]}"  # e.g., 'huggingface/squad'
            elif len(path_parts) >= 2:
                # Models and spaces need org/name format
                repo_id = f"{path_parts[0]}/{path_parts[1]}"
            else:
                return None
            
            # Check for specific file
            filename = None
            if len(path_parts) > 2:
                if 'blob' in path_parts:
                    blob_index = path_parts.index('blob')
                    if blob_index + 2 < len(path_parts):
                        # Skip 'blob' and branch name (usually 'main')
                        filename = '/'.join(path_parts[blob_index + 2:])
                elif 'resolve' in path_parts:
                    resolve_index = path_parts.index('resolve')
                    if resolve_index + 2 < len(path_parts):
                        # Skip 'resolve' and branch name (usually 'main')
                        filename = '/'.join(path_parts[resolve_index + 2:])
            
            return {
                'repo_id': repo_id,
                'repo_type': repo_type,
                'filename': filename
            }
            
        except Exception as e:
            return None
    
    def get_repository_info(self, repo_id, repo_type='model'):
        """Get repository information"""
        try:
            if repo_type == 'model':
                info = self.api.model_info(repo_id)
                files = [f.rfilename for f in info.siblings] if info.siblings else []
            elif repo_type == 'dataset':
                info = self.api.dataset_info(repo_id)
                files = [f.rfilename for f in info.siblings] if info.siblings else []
            else:
                return None
            
            return {
                'repo_id': repo_id,
                'repo_type': repo_type,
                'author': info.author if hasattr(info, 'author') else None,
                'description': getattr(info, 'description', ''),
                'tags': getattr(info, 'tags', []),
                'downloads': getattr(info, 'downloads', 0),
                'likes': getattr(info, 'likes', 0),
                'created_at': getattr(info, 'created_at', None),
                'last_modified': getattr(info, 'last_modified', None),
                'files': files,
                'total_size': sum(getattr(f, 'size', 0) for f in info.siblings) if info.siblings else 0
            }
            
        except Exception as e:
            return None
    
    def validate_token(self, token):
        """Validate Hugging Face token"""
        try:
            # Try to authenticate with the token
            api = HfApi(token=token)
            user_info = api.whoami()
            return user_info is not None
        except Exception as e:
            return False
    
    def search_models(self, query, limit=20):
        """Search for models on Hugging Face"""
        try:
            models = self.api.list_models(search=query, limit=limit)
            results = []
            
            for model in models:
                results.append({
                    'repo_id': model.modelId,
                    'author': model.author,
                    'downloads': model.downloads,
                    'likes': model.likes,
                    'tags': model.tags,
                    'created_at': model.created_at,
                    'last_modified': model.last_modified
                })
            
            return results
            
        except Exception as e:
            return []
    
    def search_datasets(self, query, limit=20):
        """Search for datasets on Hugging Face"""
        try:
            datasets = self.api.list_datasets(search=query, limit=limit)
            results = []
            
            for dataset in datasets:
                results.append({
                    'repo_id': dataset.id,
                    'author': dataset.author,
                    'downloads': dataset.downloads,
                    'likes': dataset.likes,
                    'tags': dataset.tags,
                    'created_at': dataset.created_at,
                    'last_modified': dataset.last_modified
                })
            
            return results
            
        except Exception as e:
            return []
    
    def get_model_card(self, repo_id):
        """Get model card (README) content"""
        try:
            card_data = self.api.model_info(repo_id, files_metadata=True)
            # Try to find README file
            readme_files = [f for f in card_data.siblings if f.rfilename.lower().startswith('readme')]
            
            if readme_files:
                readme_content = hf_hub_download(
                    repo_id=repo_id,
                    filename=readme_files[0].rfilename,
                    repo_type='model'
                )
                
                with open(readme_content, 'r', encoding='utf-8') as f:
                    return f.read()
            
            return None
            
        except Exception as e:
            return None
    
    def is_private_repo(self, repo_id, repo_type='model'):
        """Check if repository is private"""
        try:
            if repo_type == 'model':
                info = self.api.model_info(repo_id)
            elif repo_type == 'dataset':
                info = self.api.dataset_info(repo_id)
            else:
                return False
            
            return getattr(info, 'private', False)
            
        except RepositoryNotFoundError:
            # Might be private and we don't have access
            return True
        except Exception as e:
            return False
    
    def get_download_url(self, repo_id, filename, repo_type='model'):
        """Get direct download URL for a file"""
        try:
            url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
            if repo_type == 'dataset':
                url = f"https://huggingface.co/datasets/{repo_id}/resolve/main/{filename}"
            
            return url
            
        except Exception as e:
            return None
    
    def _format_size(self, bytes_size):
        """Format file size in human readable format"""
        if not bytes_size:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} PB"