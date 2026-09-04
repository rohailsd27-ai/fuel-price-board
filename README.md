# South Asia Fuel Price Board — self-updating setup

This folder contains a small website (`index.html`) plus a robot (`scrape.py`)
that checks fuel prices for Pakistan, India, Bangladesh and Afghanistan a few
times a day and updates the website automatically. You don't need to know how
to code to set this up — just follow the steps below once.

## What's in this folder

| File | What it's for |
|---|---|
| `index.html` | The website itself. |
| `data.json` | The current prices. The robot rewrites this file automatically. |
| `scrape.py` | The robot that fetches fresh prices. |
| `requirements.txt` | A list of tools `scrape.py` needs (handled automatically). |
| `.github/workflows/update-prices.yml` | The schedule that tells GitHub to run the robot. |

## One-time setup (about 10 minutes)

1. **Create a free GitHub account** at github.com, if you don't already have one.

2. **Create a new repository.**
   Click the "+" in the top right → "New repository" → give it a name like
   `fuel-price-board` → make sure it's set to **Public** → click "Create
   repository."

3. **Upload these files.**
   On your new repository's page, click "uploading an existing file" (or
   "Add file" → "Upload files"). Drag in all the files from this folder,
   **keeping the folder structure** — the `.github` folder needs to stay a
   folder, with `workflows` inside it, and `update-prices.yml` inside that.
   If the upload page flattens folders, you can instead create the file
   `.github/workflows/update-prices.yml` by typing that full path into the
   "Add file" → "Create new file" box, and pasting in its contents.
   Commit the changes.

4. **Give the robot permission to save its updates.**
   Go to your repository's **Settings** tab → **Actions** (in the left
   sidebar) → **General** → scroll to "Workflow permissions" → select
   **"Read and write permissions"** → **Save**.

5. **Turn on GitHub Pages, so the site gets a public web address.**
   Still in **Settings**, go to **Pages** (left sidebar) → under "Build and
   deployment," set **Source** to "Deploy from a branch" → **Branch**:
   `main`, folder `/ (root)` → **Save**.
   After a minute or two, GitHub will show you a web address like
   `https://yourusername.github.io/fuel-price-board/` — that's your live
   site, shareable with anyone.

6. **Run the robot for the first time.**
   Go to the **Actions** tab → click "Update fuel prices" in the left list →
   click **"Run workflow"** → **"Run workflow"** again to confirm. Wait
   about a minute, refresh the page, and you should see a green checkmark.
   Your site's `data.json` is now live-updated.

That's it. From now on, the robot runs automatically three times a day
(06:00, 14:00, and 22:00 UTC) with no further action needed from you.

## Checking that it's working

- Open the **Actions** tab any time to see a history of every run, and
  whether it succeeded.
- If a run shows a red X, click into it to read the log — the most common
  cause is a source website changing its page layout, which breaks the
  pattern-matching in `scrape.py`. The website itself won't show broken
  numbers in that case; it keeps the last good value and shows a small
  warning banner instead.
- You can also just open your live site and check the "Last checked" line
  under the title.

## If a source breaks and needs fixing

`scrape.py` is commented to explain what each part does. The two spots most
likely to need a small update over time are the two functions near the top:
`scrape_globalpetrolprices` and `scrape_pakistan_pakwheels`. If a source
changes its wording, those pattern-matching lines (the ones starting with
`pattern = ...`) are what need adjusting. Feel free to paste the current
content of the affected page to Claude and ask for a fix to that one
function — the rest of the setup doesn't need to change.

## Doing it manually in the meantime

Until you complete the setup above, or if you just want to double-check a
number, you can always hand-edit `data.json` directly (in Notepad, TextEdit,
or even GitHub's own file editor) and the website will show your edit next
time it's opened.
