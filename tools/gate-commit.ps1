param([string]$Message, [switch]$Push); git add .; git commit -m $Message; if ($Push) { git push }; echo "Commit completed: $Message"
