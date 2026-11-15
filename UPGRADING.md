# Upgrade an existing GitHub clone from AutoInsight v0.2 to AfterBadge v0.3

**Do not run `git init` again and do not delete your current project folder.**
The update ZIP is an overlay with only changed or new source files. It does not
contain a `.git` directory, SQLite databases, Python environments, or installed
JavaScript packages.

1. Stop both servers in the VS Code terminals with **Control + C**.
2. Save any local uncommitted edits: run `git status` and commit your work first if necessary.
3. Open your **existing** GitHub-connected project folder in VS Code. The folder
   can still be called `AutoInsight_v0.2`.
4. In its terminal, verify `ls` shows `backend`, `frontend`, and `README.md`.
5. Download `AfterBadge_v0.3_update.zip` into macOS **Downloads**. In the main
   project folder, run:

   ```bash
   unzip -o ~/Downloads/AfterBadge_v0.3_update.zip -d .
   ```

   This will update app code and README without touching your `.git` history,
   existing SQLite database, or your personally edited `.gitignore`.
6. Check `git status` to see the modified and new files.
7. In terminal 1:

   ```bash
   cd backend
   source .venv/bin/activate
   python -m pytest -q
   uvicorn app.main:app --reload
   ```

8. In terminal 2, starting from the **main project folder**:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

9. Open http://127.0.0.1:5173, import a car or open a saved one, and select
   **Problem patterns**. Click **Review source reports** on a detected pattern.
10. When you're happy, use your original project root terminal:

   ```bash
   git add README.md UPGRADING.md backend/app/main.py backend/app/service.py backend/app/patterns.py backend/tests/test_patterns.py frontend/src/App.tsx frontend/src/styles.css frontend/index.html frontend/package.json
   git commit -m "Rename project to AfterBadge and add symptom pattern explorer"
   git push origin main
   ```

Keep using your existing GitHub remote, even if the repository is named
`AutoInsight` right now. The GitHub repo name can be changed separately in
repository Settings; if you choose to rename it, update its origin URL with
`git remote set-url origin https://github.com/YOUR_USERNAME/AfterBadge.git`.

**Backward compatibility:** The default SQLite filename is still
`backend/autoinsight.db` so previously imported cars remain available.
We can rename the DB in a later migration. You do not need PostgreSQL or Docker.
