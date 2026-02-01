Deploying NGKs DL Manager (public URL)
=====================================

Option A — Deploy from Docker image (recommended)

- This repository publishes a Docker image to GitHub Container Registry (GHCR) via the workflow `.github/workflows/publish-ghcr.yml` on pushes to `main`.
- After a successful workflow run the image will be available at `ghcr.io/NGKsSystems/ngks-dl-manager-backup:latest`.

Render (example)
-----------------
1. Sign in to https://render.com and create a new service.
2. Choose "Web Service" and connect your GitHub account (authorize Render to access the repository), or choose "Private Service" and deploy from a registry image.
3. If building from the repo, select this repository and choose the Dockerfile deploy option. Set the Start Command to:

   python main.py

4. If deploying directly from the GHCR image (faster): choose "Deploy using Docker image", and enter the image reference:

   ghcr.io/NGKsSystems/ngks-dl-manager-backup:latest

   If the image is private, you will need to add a registry secret (a GitHub Personal Access Token with `read:packages`) to Render.

5. Configure any required environment variables (for example any secrets or cookies needed for downloads).
6. Deploy — Render will provide a public URL for your service.

Notes
-----
- The Actions workflow uses the repository `GITHUB_TOKEN` to publish to GHCR. Make sure the workflow runs successfully (check Actions tab) and that the image appears in your GitHub Packages.
- If you prefer another host (Fly, Railway, DigitalOcean App Platform), the same Docker image can be used.
