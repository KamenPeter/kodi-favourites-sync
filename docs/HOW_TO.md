⚙️ How Kodi on a Smart TV can sync with Google Drive

Let’s separate what’s possible natively on TV hardware versus what must be done through an intermediate device or add-on.

🥇 Best practical option — use the official “Google Drive” Kodi add-on

This is the easiest and most stable route.

How to set it up

Open Kodi → Add-ons → Download → Program Add-ons (or Video Add-ons depending on your repo).

Search for Google Drive (it’s maintained by cjcr-repo / vfs.gdrive on Kodi’s official repo or via GitHub).

Install and open it once — it will display a link and a code.

On your phone or laptop, open that link, sign in to your Google account, and approve access.

When the code pairing completes, you’ll see your Google Drive in Kodi’s file browser.

Now you can:

Browse and open your favourites.xml directly under the Google Drive source;

In the favourites-sync add-on, choose “Cloud Location → Local Path” and point it to the Google Drive virtual folder mounted by vfs.gdrive (Kodi treats it as a path starting with special://home/addons/vfs.gdrive/...).