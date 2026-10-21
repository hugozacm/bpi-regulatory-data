# One shared code checkout

GitHub repository: https://github.com/hugozacm/bpi-regulatory-data

The canonical development branch is `main`. Work in this local checkout, commit
the changes, then push to GitHub. GitHub Desktop and Codex can use the same folder;
they do not need separate copies. GitHub is the versioned shared code, not the
machine that executes Python jobs.

## Add this checkout to GitHub Desktop

Choose **File → Add local repository**, then select the folder containing this
README and `.git` directory. Select `main`, use **Fetch origin** before new work,
review changes, commit, and **Push origin**. Do not create a new repository or
clone over the running checkout. The current local folder can stay where it is;
moving it is not required for GitHub Desktop.

## What is synchronised

Python source, frontend source, configuration/mapping specifications, tests,
requirements, operational documentation and the existing workflow diagrams.

Original source archives, financial datasets, outputs, environments, logs,
credentials, test-run directories and generated Site assets are excluded.
Recreate the Python environment with requirements.txt; source-dependent tests
may skip on a clean clone. See README.md for acquisition and runtime commands.

## GitHub versus Site publication

GitHub holds the application source and documentation. The existing ChatGPT Site
has a separate managed publication checkout under `public_demo/`, ignored by the
main repository. `src/build_public_demo.py` exports from the tracked frontend
source. Use the Sites publication process for that export. A GitHub push alone
does not republish the Site or restart the running Python processor.

After changing backend code, safely restart only the owned idle processor. After
changing frontend code, regenerate and publish the existing Site. Never expose
the repository or source cache with a generic public file server.

The manual GitHub Actions acquisition workflow remains disabled unless the owner
explicitly enables REGDATA_ACTIONS_ENABLED after checking spending controls.
