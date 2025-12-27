# NGK's Download Manager

A comprehensive download manager with support for YouTube, multi-site video downloads, Hugging Face models/datasets, and direct HTTP/HTTPS downloads.

![NGK's Download Manager](screenshot.png)

## Features

### 🎥 YouTube & Video Downloads
- **YouTube video downloads** using yt-dlp
- **Multi-site support** - Twitter, Instagram, TikTok, Facebook, Vimeo, and more
- **Quality selection dialog** - Choose video quality and format
- **Audio extraction** - Download audio-only files
- **Thumbnail downloads** - Automatic thumbnail saving
- **Metadata extraction** - Video titles, descriptions, and info

### 🤗 Hugging Face Integration
- **HF_TOKEN support** - Use your Hugging Face token for authentication
- **Model downloads** - Download models with all files
- **Dataset downloads** - Complete dataset downloading
- **Private repository access** - Access gated/private content
- **Repository browser** - View model info, files, and model cards
- **Selective downloads** - Choose specific files to download

### 📁 Direct Downloads
- **HTTP/HTTPS downloads** - Regular file downloads
- **Resume capability** - Resume interrupted downloads
- **Chunked downloads** - Multi-chunk downloading for large files
- **Progress tracking** - Real-time download progress
- **Auto-retry** - Automatic retry on failures

### 🎛️ User Interface
- **Modern GUI** - Clean tkinter interface with tabs
- **Progress monitoring** - Real-time progress bars and speeds
- **Download history** - Track all downloads with timestamps
- **Settings management** - Save preferences and configurations
- **Context menus** - Right-click options for downloads
- **URL auto-detection** - Automatically detect URL types

## Installation

### Quick Setup (Windows)
1. Download or clone this repository
2. Double-click `setup.bat` to install dependencies
3. Double-click `run.bat` to start the application

### Manual Setup
1. Ensure Python 3.8+ is installed
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python main.py
   ```

### Dependencies
- `yt-dlp` - For YouTube and video site downloads
- `requests` - For HTTP downloads
- `huggingface-hub` - For Hugging Face integration
- `Pillow` - For image processing and thumbnails
- `tqdm` - For progress bars
- `beautifulsoup4` - For HTML parsing
- `tkinter` - For GUI (included with Python)

## Usage

### Basic Downloads
1. **Paste URL** - Enter any supported URL in the input field
2. **Select destination** - Choose where to save downloads
3. **Click Download** - Start the download process

### YouTube Downloads
1. Enter a YouTube URL
2. Click Download to see quality options
3. Select desired quality and format
4. Choose audio-only if needed
5. Start download

### Hugging Face Downloads
1. Enter a Hugging Face model or dataset URL
2. Set your HF_TOKEN in settings (for private repos)
3. View repository information and files
4. Choose to download all files or select specific ones

### Settings Configuration
- **Hugging Face Token** - Set in Settings tab for private repo access
- **Download preferences** - Auto-quality, audio extraction, etc.
- **Concurrent downloads** - Set maximum simultaneous downloads
- **Default destination** - Set default download folder

## Supported Sites

### Video Sites (via yt-dlp)
- YouTube (videos, playlists, channels)
- Twitter/X
- Instagram
- TikTok
- Facebook
- Vimeo
- Dailymotion
- Twitch
- SoundCloud
- Reddit
- And 1000+ more sites

### Content Platforms
- Hugging Face (models, datasets, spaces)
- Direct HTTP/HTTPS downloads
- Any site supported by yt-dlp

## Configuration

### Environment Variables
- `HF_TOKEN` - Your Hugging Face token (optional, can also be set in GUI)

### Config Files
- `config.json` - Application settings
- `download_history.json` - Download history
- Logs stored in `logs/` directory

## File Structure
```
NGKs DL Manager/
├── main.py                 # Main application
├── download_manager.py     # Direct download handler
├── youtube_downloader.py   # YouTube/video downloader
├── huggingface_downloader.py # Hugging Face integration
├── utils.py               # Utilities and helpers
├── dialogs.py             # Enhanced dialogs
├── requirements.txt       # Python dependencies
├── setup.py              # Setup script
├── setup.bat             # Windows setup
├── run.bat               # Windows launcher
└── README.md             # This file
```

## Features in Detail

### URL Detection
The application automatically detects URL types:
- **YouTube** - youtube.com, youtu.be URLs
- **Social Media** - Twitter, Instagram, TikTok, etc.
- **Hugging Face** - huggingface.co URLs
- **Direct Downloads** - Files with extensions
- **Video Sites** - Sites supported by yt-dlp

### Progress Tracking
- Real-time download progress
- Download speed monitoring
- ETA calculations
- Status updates (Starting, Downloading, Completed, Failed)

### Download Management
- Pause/resume downloads (planned)
- Cancel active downloads (planned)
- Retry failed downloads
- Queue management
- Concurrent download limits

### History & Logging
- Complete download history
- Export history to JSON
- Search download history
- Automatic logging of all operations

## Troubleshooting

### Common Issues
1. **Python not found** - Install Python 3.8+ from python.org
2. **Dependencies failed** - Run `pip install -r requirements.txt` manually
3. **yt-dlp errors** - Update yt-dlp: `pip install --upgrade yt-dlp`
4. **Hugging Face access denied** - Set valid HF_TOKEN in settings

### Getting Help
- Check the console output for error messages
- Ensure all dependencies are installed
- Verify Python version (3.8+ required)
- Check network connectivity

## Development

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

### Architecture
- `main.py` - GUI and application logic
- `download_manager.py` - Core download functionality
- `youtube_downloader.py` - yt-dlp integration
- `huggingface_downloader.py` - HF Hub integration
- `utils.py` - Utility functions and helpers
- `dialogs.py` - Enhanced dialog windows

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- **yt-dlp** - Excellent YouTube and video site downloader
- **Hugging Face** - Amazing model and dataset platform
- **Python community** - For the great libraries used

## Version History

### v1.0.0 (Current)
- Initial release
- YouTube, multi-site, and HF downloads
- GUI with progress tracking
- Quality selection dialogs
- Download history
- Resume capability
- Settings management

## Support

For support, issues, or feature requests, please open an issue on the GitHub repository.

---

**NGK's Download Manager** - Making downloads simple and powerful! 🚀